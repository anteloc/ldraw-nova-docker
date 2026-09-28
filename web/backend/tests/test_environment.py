import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import environment_config
import llm_config
import main


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_config, "_directory", tmp_path / "config")
    monkeypatch.setattr(environment_config, "_rows", [])
    monkeypatch.setattr(environment_config, "_inherited", {})
    monkeypatch.setattr(environment_config, "_initialized", False)
    yield
    environment_config._apply([])


def test_override_add_update_rename_remove_and_empty_values(monkeypatch):
    monkeypatch.setenv("LDRAW_TEST_INHERITED", "docker-value")
    monkeypatch.delenv("LDRAW_TEST_NEW", raising=False)
    monkeypatch.delenv("LDRAW_TEST_RENAMED", raising=False)
    rows = environment_config.save([
        {"name": "LDRAW_TEST_INHERITED", "value": "settings-value"},
        {"name": "LDRAW_TEST_NEW", "value": "  exact value  "},
    ])
    assert os.environ["LDRAW_TEST_INHERITED"] == "settings-value"
    assert os.environ["LDRAW_TEST_NEW"] == "  exact value  "
    assert rows[0]["value"] == "settings-value"
    rows = environment_config.save([
        {**rows[0], "value": ""},
        {**rows[1], "name": "LDRAW_TEST_RENAMED", "value": None},
    ])
    assert os.environ["LDRAW_TEST_INHERITED"] == ""  # no fallback to Docker
    assert rows[0]["has_value"] is False
    assert "LDRAW_TEST_NEW" not in os.environ
    assert os.environ["LDRAW_TEST_RENAMED"] == "  exact value  "
    environment_config.save([])
    assert os.environ["LDRAW_TEST_INHERITED"] == "docker-value"
    assert "LDRAW_TEST_RENAMED" not in os.environ


def test_references_and_provider_requests_use_override_immediately(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "inherited-key")
    client = TestClient(main.app)
    entry = llm_config.create({"litellm_params": {
        "model": "openrouter/openai/gpt-6-luna",
        "api_key": "os.environ/OPENROUTER_API_KEY"}})
    received = []

    async def completion(**params):
        received.append(params["api_key"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])

    monkeypatch.setattr(main.litellm, "acompletion", completion)
    response = client.put("/api/environment", json={"variables": [
        {"name": "OPENROUTER_API_KEY", "value": "private-override"}]})
    assert response.status_code == 200 and response.json()["variables"][0]["value"] == "private-override"
    assert client.get("/api/environment").json()["variables"][0]["value"] == "private-override"
    assert response.headers["cache-control"] == "no-store"
    assert client.post(f"/api/llm-models/{entry['id']}/test").json()["ok"]
    rows = response.json()["variables"]
    client.put("/api/environment", json={"variables": [{**rows[0], "value": "replacement-key"}]})
    assert client.post(f"/api/llm-models/{entry['id']}/test").json()["ok"]
    client.put("/api/environment", json={"variables": []})
    assert client.post(f"/api/llm-models/{entry['id']}/test").json()["ok"]
    assert received == ["private-override", "replacement-key", "inherited-key"]


def test_nested_references_and_empty_override_do_not_fall_back(monkeypatch):
    monkeypatch.setenv("LDRAW_TEST_REF", "inherited")
    rows = environment_config.save([{"name": "LDRAW_TEST_REF", "value": "override"}])
    entry = {"litellm_params": {"model": "openai/test", "extra_headers": {
        "Authorization": "os.environ/LDRAW_TEST_REF"}, "extra": ["os.environ/LDRAW_TEST_REF"]}}
    monkeypatch.setenv("LDRAW_TEST_REF", "changed-by-library")
    resolved = llm_config.resolve_params(entry)
    assert resolved["extra_headers"]["Authorization"] == "override"
    assert resolved["extra"] == ["override"]
    assert entry["litellm_params"]["extra"] == ["os.environ/LDRAW_TEST_REF"]
    environment_config.save([{**rows[0], "value": ""}])
    with pytest.raises(ValueError, match="not set or is empty"):
        llm_config.resolve_params(entry)


def test_private_persistence_is_loaded_before_backend_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("LDRAW_TEST_RESTART", "inherited")
    rows = environment_config.save([
        {"name": "LDRAW_TEST_RESTART", "value": "persisted-override"},
        {"name": "LDRAW_ASTRA_DATA_DIR", "value": str(tmp_path / "startup-data")},
    ])
    path = environment_config._directory / "environment.json"
    assert path.stat().st_mode & 0o077 == 0
    assert path.parent.stat().st_mode & 0o077 == 0
    # A new process has only the inherited environment plus the saved file.
    environment_config._apply([])
    result = subprocess.run([sys.executable, "-c", "import main, os, settings; "
        "print(os.environ['LDRAW_TEST_RESTART']); print(settings.DATA_DIR)"],
        env={**os.environ, "LDRAW_ASTRA_WEB_CONFIG_DIR": str(path.parent),
             "PYTHONPATH": str(Path(main.__file__).parent) + os.pathsep + str(Path(main.__file__).parents[2])},
        capture_output=True, text=True, check=True, timeout=30)
    assert result.stdout.splitlines() == ["persisted-override", str(tmp_path / "startup-data")]
    saved = json.loads(path.read_text())["variables"]
    assert saved[0]["id"] == rows[0]["id"]


@pytest.mark.parametrize("variables", [
    [{"name": "INVALID-NAME", "value": "private-value"}],
    [{"name": "1INVALID", "value": "private-value"}],
    [{"name": "LDRAW_TEST_BAD", "value": "private-value\0"}],
    [{"name": "LDRAW_TEST_BAD", "value": {"private-value": True}}],
    [{"name": "LDRAW_TEST_BAD", "value": None}],
    [{"id": "stale", "name": "LDRAW_TEST_BAD", "value": "private-value"}],
    [{"name": "LDRAW_TEST_BAD", "value": "private-value"}] * 2,
])
def test_invalid_updates_are_atomic_and_never_echo_values(variables):
    client = TestClient(main.app)
    previous = environment_config.save([{"name": "LDRAW_TEST_KEEP", "value": "working"}])
    response = client.put("/api/environment", json={"variables": variables})
    assert response.status_code == 400
    assert "private-value" not in response.text
    assert environment_config.public() == previous
    assert os.environ["LDRAW_TEST_KEEP"] == "working"


def test_failed_write_does_not_change_effective_environment(monkeypatch):
    previous = environment_config.save([{"name": "LDRAW_TEST_KEEP", "value": "working"}])
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(environment_config.os, "replace", fail)
    with pytest.raises(OSError):
        environment_config.save([{**previous[0], "value": "new"}])
    assert os.environ["LDRAW_TEST_KEEP"] == "working"
    assert not list(environment_config._directory.glob("*.tmp"))


def test_environment_rejects_cross_origin_changes():
    response = TestClient(main.app).put("/api/environment", headers={"origin": "https://other.example"},
        json={"variables": [{"name": "LDRAW_TEST_CROSS", "value": "private-value"}]})
    assert response.status_code == 403
    assert "LDRAW_TEST_CROSS" not in os.environ


def test_old_openrouter_name_migrates_and_standard_override_wins(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_LDRAW_ASTRA_API_KEY", "legacy-inherited")
    entry = {"litellm_params": {"model": "openrouter/openai/gpt-6-sol", "api_key": "os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY"}}
    assert llm_config.resolve_params(entry)["api_key"] == "legacy-inherited"
    rows = environment_config.save([{"name": "OPENROUTER_LDRAW_ASTRA_API_KEY", "value": "saved-legacy"}])
    assert rows[0]["name"] == "OPENROUTER_API_KEY"
    assert llm_config.resolve_params(entry)["api_key"] == "saved-legacy"
    rows = environment_config.save([{**rows[0], "value": "standard-override"}])
    assert llm_config.resolve_params(entry)["api_key"] == "standard-override"
    # An intentionally empty new key must not fall back to an old credential.
    environment_config.save([{**rows[0], "value": ""}])
    with pytest.raises(ValueError, match="empty"):
        llm_config.resolve_params(entry)
    assert llm_config.create(entry)["litellm_params"]["api_key"] == "os.environ/OPENROUTER_API_KEY"
