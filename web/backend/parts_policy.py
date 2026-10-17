"""Authoritative per-chat inventories, independent of the agent's writable files."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import sandbox
import settings
from parts_catalog import PartsCatalog, reject_custom_parts

CATALOG_VERSION = 1
CHAT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
POLICY_PROMPT = (
    "\n\nMANDATORY PARTS POLICY: Use only exact LDraw part/color pairs in the allowed catalog. "
    "Search list_allowed_parts before choosing components and colors; output/allowed-parts.csv "
    "is also available to generators. The catalog's color_id is an LDraw ID. "
    "No custom geometry or custom colors. Honor max_quantity where supplied. "
    "For JSON plans, use build --parts-palette output/allowed-parts.csv to reject violations before writing. "
    "Check candidates with check_model_parts and repair every violation. publish_model "
    "will refuse unavailable combinations. This policy also applies to all edits, including old models."
)


@lru_cache(maxsize=16)
def _load_catalog(path: str, modified: int) -> PartsCatalog:
    return PartsCatalog.load(Path(path))


def default_palette_path() -> Path | None:
    # Keep the existing variable as a compatibility alias for external CSVs.
    value = os.environ.get("NOVA_PARTS_PALETTE", os.environ.get("NOVA_PARTS_CATALOG", "")).strip()
    if not value or value == "none":
        return None
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("NOVA_PARTS_PALETTE must be none or an absolute CSV path")
    return path


class ChatPartsPolicy:
    def __init__(self, config_dir: Path, default_catalog: Path | None = None):
        self.root = config_dir / "parts-catalogs"
        self.default_catalog = default_catalog

    def path(self, chat_id: str) -> Path:
        if not CHAT_ID.fullmatch(chat_id):
            raise ValueError("Invalid Nova session identity")
        return self.root / (chat_id + ".csv")

    def load(self, chat_id: str) -> PartsCatalog | None:
        if self.path(chat_id).with_suffix(".disabled").exists():
            return None
        return self.available(chat_id)

    def available(self, chat_id: str) -> PartsCatalog | None:
        path = self.path(chat_id)
        if not path.exists():
            path = self.default_catalog
        return _load_catalog(str(path), path.stat().st_mtime_ns) if path is not None else None

    def configure(self, store, chat_id: str, content: str) -> PartsCatalog:
        catalog = PartsCatalog.from_csv(content)
        content = catalog.to_csv()
        path = self.path(chat_id)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        try:
            temporary_path.chmod(0o600)
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)
        self.set_enabled(store, chat_id, True)
        return catalog

    def _write_reference(self, store, chat_id: str, content: str) -> None:
        work = store.work_dir(chat_id)
        work.mkdir(parents=True, exist_ok=True)
        reference = work / "allowed-parts.csv"
        if reference.is_symlink():
            reference.unlink()
        reference.write_text(content, encoding="utf-8")
        sandbox.give_to_agent(reference)

    def prepare(self, store, chat_id: str) -> bool:
        """Restore the agent's read copy without changing the authoritative palette."""
        catalog = self.load(chat_id)
        if catalog is None:
            return False
        content = catalog.to_csv()
        path = self.path(chat_id)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            # Freeze defaults per chat and normalize older snapshots.
            self.configure(store, chat_id, content)
        else:
            self._write_reference(store, chat_id, content)
        return True

    def validate_model(self, chat_id: str, content: bytes) -> dict | None:
        catalog = self.load(chat_id)
        if catalog is None:
            return None
        inventory = expanded_inventory(content, settings.TOOLKIT_DIR, settings.LDRAW_DIR)
        catalog.validate(inventory)
        return {"valid": True, "physical_parts": sum(inventory.values())}

    def info(self, chat_id: str) -> dict:
        catalog = self.available(chat_id)
        return {"allowed_combinations": len(catalog.parts) if catalog else None,
                "enabled": self.load(chat_id) is not None}

    def set_enabled(self, store, chat_id: str, enabled: bool) -> None:
        """Retain the trusted palette while explicitly opting in or out per chat."""
        path = self.path(chat_id)
        marker = path.with_suffix(".disabled")
        if enabled:
            if self.available(chat_id) is None:
                raise ValueError("Upload a parts palette before enabling the restriction")
            marker.unlink(missing_ok=True)
            self.prepare(store, chat_id)
        else:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            marker.touch(mode=0o600)
            (store.work_dir(chat_id) / "allowed-parts.csv").unlink(missing_ok=True)

    def clear(self, store, chat_id: str) -> None:
        """Remove the uploaded palette."""
        path = self.path(chat_id)
        path.unlink(missing_ok=True)
        path.with_suffix(".disabled").unlink(missing_ok=True)
        (store.work_dir(chat_id) / "allowed-parts.csv").unlink(missing_ok=True)
        self.prepare(store, chat_id)


def expanded_inventory(content: bytes, toolkit_dir: Path, ldraw_dir: Path) -> dict:
    if len(content) > 32 * 1024 * 1024:
        raise ValueError("Model exceeds the parts validation limit")
    reject_custom_parts(content.decode("utf-8"))
    account = sandbox._agent_account()
    if account is None and os.geteuid() == 0:
        raise ValueError("Parts validation requires the configured unprivileged agent account")
    permissions = {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []} if account else {}
    with tempfile.TemporaryDirectory(prefix="nova-parts-check-") as directory:
        root = Path(directory)
        if account:
            os.chown(root, 0, account.pw_gid)
        root.chmod(0o750)
        model = root / "model.mpd"
        model.write_bytes(content)
        model.chmod(0o644)
        output_dir = root / "output"
        output_dir.mkdir()
        if account:
            os.chown(output_dir, account.pw_uid, account.pw_gid)
        result = subprocess.run([str(toolkit_dir / ".venv/bin/python"), "-m", "ldraw_tools.catalog_inventory",
                                 str(model), str(ldraw_dir)],
                                cwd=output_dir, **permissions,
                                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(toolkit_dir),
                                     "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(output_dir)},
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=120)
        if len(result.stdout) > 32 * 1024 * 1024:
            raise ValueError("Physical model exceeds the parts validation limit")
        return {(part, color): quantity for part, color, quantity in json.loads(result.stdout)}


policy = ChatPartsPolicy(settings.CONFIG_DIR, default_palette_path())
