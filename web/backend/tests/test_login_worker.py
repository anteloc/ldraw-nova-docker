import asyncio
import base64
import io
import json
from pathlib import Path

import pytest

import browser_auth
import login_worker


def jwt(claims):
    return "header." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".signature"


@pytest.fixture
def auth(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path))
    monkeypatch.setenv("CHATGPT_AUTH_FILE", "auth.json")
    return login_worker.Authenticator()


def token_record():
    return {"tokens": {"access_token": jwt({"exp": 2_000_000_000}), "refresh_token": "private-refresh",
                       "id_token": jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "test-account"}})}}


def test_browser_login_uses_official_browser_flow_and_imports_session(auth, monkeypatch, capsys):
    sent = io.StringIO()
    private_home = Path(auth.token_dir) / "codex"
    url = "https://auth.openai.com/oauth/authorize?response_type=code&state=opaque&code_challenge=pkce"
    messages = [
        {"id": 1, "result": {}},
        {"id": 2, "result": {"type": "chatgpt", "loginId": "login-123", "authUrl": url}},
        {"method": "account/login/completed", "params": {"loginId": "unrelated", "success": False}},
        {"method": "account/login/completed", "params": {"loginId": "login-123", "success": True}},
    ]
    class Process:
        def __init__(self, command, **kwargs):
            assert command[:4] == ["codex", "app-server", "--listen", "stdio://"]
            assert kwargs["env"]["CODEX_HOME"] == str(private_home)
            assert "OPENAI_API_KEY" not in kwargs["env"]
            assert 'cli_auth_credentials_store="file"' in command
            self.stdin = sent
            self.stdout = io.StringIO("\n".join(json.dumps(m) for m in messages))
            (private_home / "auth.json").write_text(json.dumps(token_record()))
        def poll(self): return None
        def terminate(self): pass
        def communicate(self, **kwargs): return ("", "")
    monkeypatch.setattr(login_worker.subprocess, "Popen", Process)
    monkeypatch.setattr(login_worker.time, "sleep", lambda _: None)
    login_worker.browser_login()
    requests = [json.loads(line) for line in sent.getvalue().splitlines()]
    assert requests[-1]["method"] == "account/login/start"
    assert requests[-1]["params"] == {"type": "chatgpt", "useHostedLoginSuccessPage": True, "appBrand": "chatgpt"}
    out = capsys.readouterr().out
    assert json.loads(out) == {"type": "login", "flow": "browser", "url": url}
    assert "private-refresh" not in out and '"code"' not in out
    stored = json.loads(Path(auth.auth_file).read_text())
    assert stored["account_id"] == "test-account" and stored["expires_at"] == 2_000_000_000
    assert stored["refresh_token"] == "private-refresh"
    assert Path(auth.auth_file).stat().st_mode & 0o077 == 0
    assert not (private_home / "auth.json").exists()


def test_incomplete_login_cannot_replace_working_credentials(auth):
    target = Path(auth.auth_file)
    target.write_text('{"refresh_token":"previous-working-session"}')
    private_home = Path(auth.token_dir) / "codex"
    private_home.mkdir()
    (private_home / "auth.json").write_text('{"tokens":{"access_token":"incomplete"}}')
    with pytest.raises(ValueError, match="complete ChatGPT session"):
        login_worker.import_credentials(private_home, auth)
    assert json.loads(target.read_text())["refresh_token"] == "previous-working-session"


@pytest.mark.parametrize("success", [True, False])
def test_parent_handles_browser_worker_without_device_code(monkeypatch, success):
    events = [{"type": "login", "flow": "browser", "url": "https://auth.openai.com/oauth/authorize?state=test"}]
    if not success:
        events.append({"type": "login_error", "message": "Retry browser sign-in."})
    class Reader:
        def __init__(self): self.parts = iter([json.dumps(e).encode() + b"\n" for e in events] + [b""])
        async def read(self, size): return next(self.parts)
    class Process:
        stdout = Reader()
        returncode = 0 if success else 1
        async def wait(self): return self.returncode
    async def spawn(*command, **kwargs):
        assert "--device" not in command
        return Process()
    async def connected(provider): return success
    monkeypatch.setattr(browser_auth.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(browser_auth, "connected", connected)
    state = {"status": "starting", "flow": "browser"}
    asyncio.run(browser_auth._login("openai", state))
    assert state["status"] == ("connected" if success else "error")
    assert "code" not in state
    if not success:
        assert state["message"] == "Retry browser sign-in."


def test_switching_from_device_to_browser_cancels_old_login(monkeypatch):
    flows = []
    cancelled = []
    async def login(provider, state):
        flows.append(state["flow"])
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.append(state["flow"])
            raise
    monkeypatch.setattr(browser_auth, "_login", login)
    monkeypatch.setattr(browser_auth, "_sessions", {})
    monkeypatch.setattr(browser_auth, "_locks", {})
    async def run():
        await browser_auth.start("openai", "device")
        await asyncio.sleep(0)
        # An explicit retry after changing account settings must mint a fresh code.
        await browser_auth.start("openai", "device", restart=True)
        await asyncio.sleep(0)
        assert cancelled == ["device"] and flows == ["device", "device"]
        result = await browser_auth.start("openai")
        await asyncio.sleep(0)
        assert result == {"status": "starting", "flow": "browser"}
        assert cancelled == ["device", "device"] and flows == ["device", "device", "browser"]
        await browser_auth.shutdown()
    asyncio.run(run())


def test_device_flow_remains_explicit_and_does_not_change_claude():
    with pytest.raises(ValueError, match="Unsupported login flow"):
        asyncio.run(browser_auth.start("anthropic", "device"))
