"""Single-user browser sessions, isolated from the agent's writable workspace.

Only provider-issued URLs and device codes are returned to the browser. Tokens
stay in /config. Login subprocesses can be cancelled and never run inference.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import settings

PROVIDERS = ("openai", "anthropic")
_sessions: dict[str, dict] = {}
_locks: dict[str, asyncio.Lock] = {}


def auth_dir(provider: str) -> Path:
    if provider not in PROVIDERS:
        raise ValueError("Unknown login provider")
    settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(settings.CONFIG_DIR, 0o700)
    path = settings.CONFIG_DIR / "browser" / provider
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def claude_binary() -> str:
    import claude_agent_sdk
    return str(Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude")


def claude_env() -> dict[str, str]:
    # Explicitly erase inherited API credentials even when an SDK merges envs.
    return {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(auth_dir("anthropic")), "CLAUDE_CONFIG_DIR": str(auth_dir("anthropic")),
            "ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "CLAUDE_CODE_OAUTH_TOKEN": "",
            "CLAUDECODE": "", "BROWSER": "/bin/true", "TERM": "dumb",
            "DISABLE_AUTOUPDATER": "1"}


def openai_authenticator():
    from litellm.llms.chatgpt.authenticator import Authenticator
    os.environ["CHATGPT_TOKEN_DIR"] = str(auth_dir("openai"))
    os.environ["CHATGPT_AUTH_FILE"] = "auth.json"
    return Authenticator()


async def openai_ready() -> None:
    """Refresh before inference; never silently start a login from a chat turn."""
    auth = openai_authenticator()
    data = auth._read_auth_file() or {}
    token = data.get("access_token")
    if token and not auth._is_token_expired(data, token):
        return
    if data.get("refresh_token"):
        try:
            await asyncio.to_thread(auth._refresh_tokens, data["refresh_token"])
            os.chmod(auth.auth_file, 0o600)
            return
        except Exception:
            pass
    raise ValueError("ChatGPT login expired or missing. Sign in again in Settings.")


async def connected(provider: str) -> bool:
    if provider == "openai":
        data = openai_authenticator()._read_auth_file() or {}
        return bool(data.get("access_token") and data.get("refresh_token"))
    proc = await asyncio.create_subprocess_exec(
        claude_binary(), "auth", "status", env=claude_env(),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), 15)
        return proc.returncode == 0 and bool(json.loads(stdout).get("loggedIn"))
    except (asyncio.TimeoutError, ValueError):
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        return False


async def status(provider: str) -> dict:
    auth_dir(provider)
    state = _sessions.get(provider, {})
    if state.get("status") in ("starting", "pending", "error", "expired"):
        return {k: v for k, v in state.items() if k in ("status", "url", "code", "expires_at", "message", "flow")}
    return {"status": "connected" if await connected(provider) else "disconnected"}


async def _stop(provider: str):
    state = _sessions.pop(provider, {})
    task = state.get("task")
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def start(provider: str, flow: str = "browser", restart: bool = False) -> dict:
    auth_dir(provider)
    if flow not in ("browser", "device") or (provider != "openai" and flow != "browser"):
        raise ValueError("Unsupported login flow")
    async with _locks.setdefault(provider, asyncio.Lock()):
        current = _sessions.get(provider, {})
        if not restart and current.get("status") in ("starting", "pending") and current.get("flow", "browser") == flow:
            return await status(provider)
        await _stop(provider)
        state = {"status": "starting", "expires_at": time.time() + 900, "flow": flow}
        _sessions[provider] = state
        state["task"] = asyncio.create_task(_login(provider, state))
        return {"status": "starting", "flow": flow}


async def _login(provider: str, state: dict):
    proc = None
    try:
        if provider == "openai":
            env = {**os.environ, "CHATGPT_TOKEN_DIR": str(auth_dir(provider)), "CHATGPT_AUTH_FILE": "auth.json"}
            command = [sys.executable, "-u", str(Path(__file__).with_name("login_worker.py"))]
            if state.get("flow") == "device":
                command.append("--device")
        else:
            env = claude_env()
            command = [claude_binary(), "auth", "login", "--claudeai"]
        proc = await asyncio.create_subprocess_exec(*command, env=env, cwd=auth_dir(provider),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        state["process"] = proc
        async with asyncio.timeout(900):
            buffer = ""
            while data := await proc.stdout.read(4096):
                buffer = (buffer + data.decode(errors="replace"))[-32_000:]
                clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", buffer)
                if provider == "openai":
                    for line in clean.splitlines():
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if event.get("type") == "login":
                            state.update(status="pending", url=event["url"], flow=event.get("flow", "browser"))
                            if event.get("code"):
                                state["code"] = event["code"]
                        elif event.get("type") == "login_error":
                            state.update(status="error", message=event["message"])
                else:
                    for url in re.findall(r"https://[^\s\x1b]+(?=\s)", clean):
                        if urlsplit(url).hostname in ("claude.ai", "platform.claude.com", "console.anthropic.com"):
                            state.update(status="pending", url=url)
            await proc.wait()
            if proc.returncode == 0 and await connected(provider):
                state.clear()
                state["status"] = "connected"
            elif state.get("status") != "error":
                state.update(status="error", message="Login did not complete. Retry the sign-in flow.")
    except TimeoutError:
        state.update(status="expired", message="Login expired. Start again.")
    except asyncio.CancelledError:
        raise
    except Exception:
        state.update(status="error", message="Unable to start provider login. Check the installed runtime and network.")
    finally:
        if proc and proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
        # The SDK/provider controls file contents; make its credential cache private.
        for path in auth_dir(provider).rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(0o600)
        if provider == "openai":
            (auth_dir(provider) / "codex" / "auth.json").unlink(missing_ok=True)


async def submit_code(provider: str, code: str):
    state = _sessions.get(provider, {})
    proc = state.get("process")
    if provider != "anthropic" or state.get("status") != "pending" or not proc or proc.returncode is not None:
        raise ValueError("No Claude login is awaiting a code")
    if not code.strip() or len(code) > 4096 or "\n" in code or "\r" in code:
        raise ValueError("Invalid authorization code")
    proc.stdin.write((code.strip() + "\n").encode())
    await proc.stdin.drain()


async def disconnect(provider: str):
    auth_dir(provider)
    await _stop(provider)
    if provider == "openai":
        Path(openai_authenticator().auth_file).unlink(missing_ok=True)
    else:
        proc = await asyncio.create_subprocess_exec(claude_binary(), "auth", "logout", env=claude_env(),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.wait_for(proc.wait(), 15)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ValueError("Logout timed out; retry") from None


async def shutdown():
    for provider in list(_sessions):
        await _stop(provider)
