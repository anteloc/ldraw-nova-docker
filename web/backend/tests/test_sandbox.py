import asyncio
import os
from pathlib import Path

import pytest

import llm_config
import sandbox
import settings

needs_agent_user = pytest.mark.skipif(sandbox._agent_account() is None, reason="needs root + the `agent` user (run in the container)")


@needs_agent_user
def test_runs_as_agent_without_access_to_keys(tmp_path: Path):
    llm_config.create({"litellm_params": {"model": "openai/gpt-6-luna", "api_key": "sk-top-secret"}})
    result = asyncio.run(sandbox.run(
        ["bash", "-c", f"id -un; env; cat {settings.CONFIG_DIR / 'models.json'}"], tmp_path / "ws", timeout=20))
    assert result.stdout.splitlines()[0] == "agent"
    assert "Permission denied" in result.stderr
    assert "sk-top-secret" not in result.stdout + result.stderr
    assert "API_KEY" not in result.stdout                      # scrubbed environment


def test_timeout_kills_the_whole_process_group(tmp_path: Path):
    result = asyncio.run(sandbox.run(["bash", "-c", "sleep 30 & sleep 30"], tmp_path / "ws", timeout=1))
    assert result.timed_out and result.exit_code is None and result.seconds < 10


def test_output_is_truncated(tmp_path: Path):
    result = asyncio.run(sandbox.run(["python3", "-c", "print('x' * 100000)"], tmp_path / "ws", timeout=20))
    assert len(result.stdout) < 25_000 and "characters omitted" in result.stdout


@needs_agent_user
def test_agent_can_render_with_leocad(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "m.ldr").write_text("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
    os.chmod(ws, 0o777)
    result = asyncio.run(sandbox.run(["leocad", "m.ldr", "-i", "m.png", "-w", "200", "-h", "150"], ws, timeout=120))
    assert result.exit_code == 0, result.as_text()
    assert (ws / "m.png").stat().st_size > 500


def test_output_arrives_before_command_finishes_and_redacts_split_secret(tmp_path):
    async def check():
        output = []
        seen = asyncio.Event()
        def receive(channel, text):
            output.append(text)
            seen.set()
        code = "import sys,time; print('started', flush=True); time.sleep(.2); sys.stdout.write('private-'); sys.stdout.flush(); time.sleep(.2); print('test-value', flush=True); time.sleep(2)"
        task = asyncio.create_task(sandbox.run(["python3", "-u", "-c", code], tmp_path / "live", 10,
            on_output=receive, secrets=("private-test-value",)))
        await asyncio.wait_for(seen.wait(), 2)
        assert not task.done()
        result = await task
        assert "private-test-value" not in result.stdout + "".join(output)
        assert "[redacted]" in result.stdout
    asyncio.run(check())


def test_orphan_child_holding_stdout_is_also_bounded(tmp_path):
    result = asyncio.run(sandbox.run(["bash", "-c", "sleep 30 & exit 0"], tmp_path / "orphan", 1))
    assert result.timed_out and result.seconds < 10
