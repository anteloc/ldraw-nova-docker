"""Local quantities and explicit catalogue-to-LDraw normalization."""

from __future__ import annotations
from contextlib import contextmanager
import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
import xml.etree.ElementTree as ET
import settings

MAX_UPLOAD = 2 * 1024 * 1024
MAX_LOTS = 10000
MAX_QUANTITY = 1000000


def directory():
    path = settings.DATA_DIR / "parts"
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


@contextmanager
def connection():
    db = sqlite3.connect(directory() / "owned.sqlite", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE IF NOT EXISTS lots (id TEXT PRIMARY KEY, part TEXT, color INTEGER, quantity INTEGER NOT NULL, raw_part TEXT NOT NULL, raw_color TEXT NOT NULL, system TEXT NOT NULL, label TEXT NOT NULL)"
    )
    try:
        with db:
            yield db
    finally:
        db.close()


def normal(value):
    return re.sub(r"[^a-z0-9]", "", value.lower().replace("gray", "grey"))


def palette():
    result = []
    for line in (
        (settings.LDRAW_DIR / "LDConfig.ldr").read_text(errors="replace").splitlines()
    ):
        m = re.match(
            r"0\s+!COLOUR\s+(\S+)\s+CODE\s+(\d+)\s+VALUE\s+(#[a-fA-F0-9]{6})", line
        )
        if m and int(m[2]) not in (16, 24):
            result.append(
                {"code": int(m[2]), "name": m[1].replace("_", " "), "hex": m[3]}
            )
    return result


def color_named(name):
    aliases = {
        "darkpurple": "mediumlilac",
        "transclear": "transclear",
        "umber": "umberbrown",
        "sienna": "siennabrown",
    }
    wanted = aliases.get(normal(name), normal(name))
    matches = [c["code"] for c in palette() if normal(c["name"]) == wanted]
    return matches[0] if len(matches) == 1 else None


def valid_part(value):
    part = str(value).strip().lower().removesuffix(".dat")
    if not re.fullmatch(r"[a-z0-9_-]{1,80}", part):
        raise ValueError("Use a part number, without a path")
    path = settings.LDRAW_DIR / "parts" / (part + ".dat")
    return part if path.is_file() and not path.is_symlink() else None


def positive(value):
    if (
        isinstance(value, bool)
        or not re.fullmatch(r"[0-9]+", str(value))
        or not 1 <= int(value) <= MAX_QUANTITY
    ):
        raise ValueError("Quantity must be a whole number from 1 to 1,000,000")
    return int(value)


def normalize(rows, system):
    if system not in ("ldraw", "bricklink", "rebrickable"):
        raise ValueError("Choose LDraw, BrickLink or Rebrickable IDs")
    from parts_catalog import color_map

    mapping = color_map(system) if system != "ldraw" else {}
    colors = {c["code"] for c in palette()}
    result = []
    for row in rows:
        if len(result) >= MAX_LOTS:
            raise ValueError("Import at most 10,000 lots")
        raw_part, raw_color = str(row["part"]).strip(), str(row["color"]).strip()
        part = valid_part(raw_part)
        if system == "ldraw":
            color = (
                int(raw_color)
                if re.fullmatch(r"[0-9]+", raw_color)
                else color_named(raw_color)
            )
            if color not in colors:
                color = None
        else:
            color = (
                mapping.get(raw_color)
                if raw_color.isdigit()
                else color_named(raw_color)
            )
        result.append(
            {
                "part": part,
                "color": color,
                "quantity": positive(row["quantity"]),
                "raw_part": raw_part,
                "raw_color": raw_color,
                "system": system,
            }
        )
    if not result:
        raise ValueError("No physical part lots found")
    if sum(r["quantity"] for r in result) > MAX_QUANTITY:
        raise ValueError("Keep the inventory below 1,000,000 pieces per import")
    return result


def parse_upload(raw, system):
    if len(raw) > MAX_UPLOAD:
        raise ValueError("Parts list exceeds 2 MB")
    text = raw.decode("utf-8-sig")
    if text.lstrip().startswith("<"):
        if "<!" in text:
            raise ValueError("XML declarations with entities or DTDs are not supported")
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            raise ValueError("Invalid BrickLink XML") from None
        rows = []
        for item in root.findall(".//ITEM"):
            if item.findtext("ITEMTYPE", "P") != "P":
                raise ValueError(
                    "Upload physical parts only; use set numbers or set links for complete set inventories"
                )
            rows.append(
                {
                    "part": item.findtext("ITEMID", ""),
                    "color": item.findtext("COLOR", ""),
                    "quantity": item.findtext("QTY") or item.findtext("MINQTY") or "1",
                }
            )
        return normalize(rows, "bricklink")
    reader = csv.DictReader(io.StringIO(text))
    keys = {normal(k): k for k in reader.fieldnames or []}

    def key(options):
        return next((keys[k] for k in options if k in keys), None)

    part = key(["partid", "partnum", "part", "itemid", "ldrawid"])
    color = key(
        ["colorcode", "colourcode", "colorid", "color", "colour", "ldrawcolorid"]
    )
    qty = key(["quantity", "qty", "minqty"])
    if not all((part, color, qty)):
        raise ValueError(
            "CSV needs part_id, color and quantity columns (Nova BOM and Rebrickable exports are supported)"
        )
    if "colorcode" in keys or "ldrawcolorid" in keys:
        system = "ldraw"
    return normalize(
        ({"part": r[part], "color": r[color], "quantity": r[qty]} for r in reader),
        system,
    )


def add(rows, label):
    if not label.strip() or len(label) > 80 or any(ord(c) < 32 for c in label):
        raise ValueError("Use a label from 1 to 80 characters")
    with connection() as db:
        if db.execute("SELECT count(*) FROM lots").fetchone()[0] + len(rows) > MAX_LOTS:
            raise ValueError("Keep at most 10,000 owned lots")
        if (
            db.execute("SELECT coalesce(sum(quantity),0) FROM lots").fetchone()[0]
            + sum(r["quantity"] for r in rows)
            > MAX_QUANTITY
        ):
            raise ValueError("Keep at most 1,000,000 owned pieces")
        db.executemany(
            "INSERT INTO lots VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    uuid.uuid4().hex,
                    r["part"],
                    r["color"],
                    r["quantity"],
                    r["raw_part"],
                    r["raw_color"],
                    r["system"],
                    label.strip(),
                )
                for r in rows
            ],
        )
    return inventory()


def inventory(query=""):
    with connection() as db:
        rows = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM lots ORDER BY label, raw_part, raw_color"
            )
        ]
    usable = [r for r in rows if r["part"] is not None and r["color"] is not None]
    return {
        "lots": [
            r
            for r in rows
            if query.casefold() in (r["raw_part"] + " " + r["label"]).casefold()
        ],
        "total": sum(r["quantity"] for r in rows),
        "usable": sum(r["quantity"] for r in usable),
        "unmapped": len(rows) - len(usable),
        "palette": palette(),
    }


def edit(lot, part, color, quantity):
    resolved = valid_part(part)
    if (
        resolved is None
        or type(color) is not int
        or color not in {c["code"] for c in palette()}
    ):
        raise ValueError("Choose an installed part and explicit LDraw color")
    qty = positive(quantity)
    with connection() as db:
        old = db.execute("SELECT quantity FROM lots WHERE id=?", (lot,)).fetchone()
        if old is None:
            raise ValueError("Lot not found")
        total = db.execute("SELECT sum(quantity) FROM lots").fetchone()[0]
        if total - old[0] + qty > MAX_QUANTITY:
            raise ValueError("Keep at most 1,000,000 owned pieces")
        db.execute(
            "UPDATE lots SET part=?,color=?,quantity=? WHERE id=?",
            (resolved, color, qty, lot),
        )
    return inventory()


def snapshot():
    from collections import Counter

    with connection() as db:
        rows = db.execute(
            "SELECT part,color,quantity FROM lots WHERE part IS NOT NULL AND color IS NOT NULL"
        ).fetchall()
    counts = Counter()
    for r in rows:
        counts[(r[0], r[1])] += r[2]
    lots = [
        {"part": p, "color": c, "quantity": q} for (p, c), q in sorted(counts.items())
    ]
    raw = json.dumps(lots, sort_keys=True).encode()
    return {"revision": hashlib.sha256(raw).hexdigest(), "lots": lots}


def capture(store, chat_id):
    """Authoritative backend-owned copy; the writable work copy is guidance."""
    import sandbox

    stock = snapshot()
    if not stock["lots"]:
        raise ValueError(
            "Add usable inventory in My Parts before selecting Use my parts"
        )
    raw = json.dumps(stock)
    canonical = store.chat_dir(chat_id) / "owned-parts.snapshot.json"
    canonical.write_text(raw)
    canonical.chmod(0o644)
    guidance = store.work_dir(chat_id) / "owned-parts.json"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    guidance.write_text(raw)
    sandbox.give_to_agent(guidance)
    return stock


def saved_report(model):
    """Only show a fitting report for the exact saved model revision."""
    sidecar = model.with_suffix(".inventory.json")
    if (
        sidecar.is_symlink()
        or not sidecar.is_file()
        or sidecar.stat().st_size > 2 * 1024 * 1024
        or model.stat().st_size > 32 * 1024 * 1024
    ):
        return None
    try:
        report = json.loads(sidecar.read_text())
        if report.get("model_sha256") != hashlib.sha256(model.read_bytes()).hexdigest():
            return None
        keys = (
            "total_parts",
            "matched_parts",
            "missing_parts",
            "color_changes",
            "splits",
        )
        if any(type(report.get(k)) is not int or report[k] < 0 for k in keys):
            return None
        if report["matched_parts"] + report["missing_parts"] != report["total_parts"]:
            return None
        if not isinstance(report.get("missing"), list):
            return None
        for lot in report["missing"]:
            if (
                not isinstance(lot, dict)
                or not re.fullmatch(r"[a-z0-9_-]{1,80}", str(lot.get("part", "")))
                or type(lot.get("color")) is not int
                or type(lot.get("quantity")) is not int
                or lot["quantity"] < 1
            ):
                return None
        return {**{k: report[k] for k in keys}, "missing": report["missing"]}
    except (OSError, ValueError, TypeError, AttributeError):
        return None
