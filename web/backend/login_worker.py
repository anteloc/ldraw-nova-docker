"""OpenAI sign-in worker. stdout carries UI instructions, never credentials.

The official app-server owns browser OAuth, PKCE, state validation, and its
loopback callback. On success, translate its private cache for LiteLLM, which
continues to own inference and refresh. Device flow is an explicit fallback.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from litellm.llms.chatgpt.authenticator import Authenticator
from litellm.llms.chatgpt.common_utils import CHATGPT_DEVICE_VERIFY_URL


def emit(**event):
    print(json.dumps(event), flush=True)


def import_credentials(codex_home: Path, auth: Authenticator):
    path = codex_home / "auth.json"
    tokens = json.loads(path.read_text()).get("tokens", {})
    if not all(isinstance(tokens.get(k), str) and tokens[k] for k in ("access_token", "refresh_token", "id_token")):
        raise ValueError("Login did not produce a complete ChatGPT session")
    # Atomic replacement preserves any previous working session if import fails.
    target = Path(auth.auth_file)
    tmp = target.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(auth._build_auth_record(tokens), stream)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    # Only LiteLLM should refresh this session, avoiding two rotating caches.
    path.unlink()


def browser_login():
    auth = Authenticator()
    codex_home = Path(auth.token_dir) / "codex"
    codex_home.mkdir(mode=0o700, exist_ok=True)
    # A previous interrupted login may have left an unimported credential.
    (codex_home / "auth.json").unlink(missing_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
           "HOME": str(codex_home), "CODEX_HOME": str(codex_home),
           "BROWSER": "/bin/true", "RUST_LOG": "off"}
    proc = subprocess.Popen(
        ["codex", "app-server", "--listen", "stdio://", "-c", 'cli_auth_credentials_store="file"'],
        env=env, cwd=codex_home, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    )

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(response_id):
        while line := proc.stdout.readline():
            message = json.loads(line)
            if message.get("id") == response_id:
                if "error" in message:
                    raise ValueError("OpenAI login runtime rejected the request")
                return message["result"]
        raise ValueError("OpenAI login runtime exited")

    try:
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "ldraw_nova", "title": "LDraw Nova", "version": "0.1.0"},
            "capabilities": {"experimentalApi": False}}})
        receive(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/login/start", "params": {
            "type": "chatgpt", "useHostedLoginSuccessPage": True, "appBrand": "chatgpt"}})
        login = receive(2)
        url = login["authUrl"]
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ("auth.openai.com", "chatgpt.com"):
            raise ValueError("Unexpected OpenAI authorization URL")
        emit(type="login", flow="browser", url=url)
        while line := proc.stdout.readline():
            message = json.loads(line)
            if message.get("method") != "account/login/completed":
                continue
            result = message["params"]
            if result.get("loginId") != login["loginId"]:
                continue
            if not result.get("success"):
                raise ValueError("OpenAI authorization was not completed")
            import_credentials(codex_home, auth)
            # Allow the runtime to finish delivering the browser's success redirect.
            time.sleep(2)
            return
        raise ValueError("OpenAI login ended before authorization completed")
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        (codex_home / "auth.json").unlink(missing_ok=True)


class DeviceAuthenticator(Authenticator):
    def login(self):
        code = self._request_device_code()
        emit(type="login", flow="device", url=CHATGPT_DEVICE_VERIFY_URL, code=code["user_code"])
        authorization = self._poll_for_authorization_code(code)
        tokens = self._exchange_code_for_tokens(authorization)
        self._write_auth_file(self._build_auth_record(tokens))


if __name__ == "__main__":
    os.umask(0o077)
    try:
        if "--device" in sys.argv:
            DeviceAuthenticator().login()
        else:
            browser_login()
    except Exception:
        # Exceptions and runtime output may contain auth responses: never relay them.
        emit(type="login_error", message="OpenAI sign-in did not complete. Retry, and make sure the app's callback port 1455 is available.")
        raise SystemExit(1)
