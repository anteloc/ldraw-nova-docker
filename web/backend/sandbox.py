"""Run agent-written code as the unprivileged `agent` user.

The server runs as root inside the container; tool subprocesses drop to
`agent`, get a scrubbed environment (no API keys) and a CPU/file-size limit,
and run in the chat's workspace folder. /config (root, 0700) is unreadable to
them. This is meant for a local single-user tool, not hostile multi-tenancy.
"""
from __future__ import annotations

import asyncio
import codecs
import os
import pwd
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

AGENT_USER = os.environ.get("LDRAW_NOVA_AGENT_USER", "agent")
MAX_OUTPUT_CHARS = 20_000
MAX_FILE_BYTES = 512 * 1024 * 1024

# Only what renders and Python need; notably nothing from the server's env.
# UV_PYTHON_INSTALL_DIR: uv finds the image's Python 3.14 instead of downloading one.
PASSTHROUGH_ENV = ("DISPLAY", "LEOCAD_LIB", "LIBGL_ALWAYS_SOFTWARE", "PYTHONPATH", "LDRAW_NOVA_DATA_DIR",
                   "UV_PYTHON_INSTALL_DIR")
# The repo's scripts/ (mpd2glb.sh, ...), on the agents' PATH too.
SCRIPTS_DIR = os.environ.get("LDRAW_NOVA_SCRIPTS_DIR", "/opt/scripts")


@dataclass
class RunResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    seconds: float

    def as_text(self) -> str:
        status = "timed out (killed)" if self.timed_out else f"exit code {self.exit_code}"
        parts = [f"[{status}, {self.seconds:.1f}s]"]
        if self.stdout:
            parts.append("--- stdout ---\n" + self.stdout)
        if self.stderr:
            parts.append("--- stderr ---\n" + self.stderr)
        return "\n".join(parts)


def _agent_account():
    if os.geteuid() != 0:
        return None                         # dev on a host: run as ourselves
    try:
        return pwd.getpwnam(AGENT_USER)
    except KeyError:
        return None


def give_to_agent(path: Path) -> None:
    """Let the agent user modify files the server wrote into its workspace."""
    account = _agent_account()
    if account is None:
        return
    try:
        os.chown(path, account.pw_uid, account.pw_gid)
    except OSError:
        pass                                # e.g. bind mounts that ignore chown


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    half = MAX_OUTPUT_CHARS // 2
    return f"{text[:half]}\n... [{len(text) - MAX_OUTPUT_CHARS} characters omitted] ...\n{text[-half:]}"


async def run(argv: list[str], cwd: Path, timeout: int, *,
              env_extra: dict[str, str] | None = None,
              on_output: Callable[[str, str], None] | None = None,
              secrets: tuple[str, ...] = ()) -> RunResult:
    cwd.mkdir(parents=True, exist_ok=True)
    account = _agent_account()
    home = Path(account.pw_dir) if account else cwd
    env = {
        "PATH": f"{SCRIPTS_DIR}:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "XDG_RUNTIME_DIR": f"/tmp/runtime-{AGENT_USER}" if account else os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
        **{k: os.environ[k] for k in PASSTHROUGH_ENV if k in os.environ},
        **(env_extra or {}),
    }
    # Limits via the shell rather than preexec_fn (unsafe in a threaded server).
    command = [
        "bash", "-c",
        f'ulimit -t {timeout + 5}; ulimit -f {MAX_FILE_BYTES // 1024}; exec "$@"', "--", *argv,
    ]
    if account:
        give_to_agent(cwd)
        # asyncio's subprocess API doesn't take user=/group=, so drop privileges
        # with util-linux's setpriv instead.
        command = ["setpriv", f"--reuid={account.pw_uid}", f"--regid={account.pw_gid}",
                   "--clear-groups", "--", *command]
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *command, cwd=cwd, env=env, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    # Drain both pipes continuously, but retain bounded head/tail buffers. Long
    # renders and index builds must neither block the event loop nor exhaust RAM.
    async def drain(pipe, channel):
        head, tail, total, pending = "", "", 0, ""
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        keep = max((len(s) for s in secrets if s), default=1) - 1

        def accept(text):
            nonlocal head, tail, total
            total += len(text)
            half = MAX_OUTPUT_CHARS // 2
            if len(head) < half:
                take = min(half - len(head), len(text))
                head += text[:take]
                text = text[take:]
            tail = (tail + text)[-MAX_OUTPUT_CHARS:]

        while True:
            block = await pipe.read(4096)
            pending += decoder.decode(block, final=not block)
            # Replace complete secrets before splitting, retaining enough suffix
            # to catch a credential split across adjacent pipe reads.
            for secret in secrets:
                if secret:
                    pending = pending.replace(secret, "[redacted]")
            n = len(pending) if not block else max(0, len(pending) - keep)
            text, pending = pending[:n], pending[n:]
            accept(text)
            if text and on_output:
                on_output(channel, text)
            if not block:
                break
        if total <= MAX_OUTPUT_CHARS:
            return head + tail
        return f"{head}\n... [{total - MAX_OUTPUT_CHARS} characters omitted] ...\n{tail[-MAX_OUTPUT_CHARS // 2:]}"

    readers = [asyncio.create_task(drain(proc.stdout, "stdout")), asyncio.create_task(drain(proc.stderr, "stderr"))]

    async def finish():
        await proc.wait()
        return await asyncio.gather(*readers)

    completion = asyncio.create_task(finish())
    try:
        await asyncio.wait_for(asyncio.shield(completion), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        timed_out = isinstance(exc, asyncio.TimeoutError)
        try:
            os.killpg(proc.pid, signal.SIGKILL)   # the whole group: shells spawn children
        except ProcessLookupError:
            pass
        await completion
        if not timed_out:
            raise
    out, err = await completion
    return RunResult(
        exit_code=None if timed_out else proc.returncode,
        stdout=out,
        stderr=err,
        timed_out=timed_out,
        seconds=time.monotonic() - started,
    )
