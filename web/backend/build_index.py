"""Build the search indexes the agent tools use. Run once at image build time:

    python3 build_index.py <ldraw-dir> <ref-models-dir> <out-dir>

Writes:
  parts.json       [[id, description, category, keywords, type], ...] for parts/*.dat
  ref-models.json  [{"file", "parts", "submodels": [{"name", "description"}]}, ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

META_PREFIXES = ("Name:", "Author:", "!", "//", "BFC", "STEP", "ROTATION", "FILE", "NOFILE")


def _read_lines(path: Path, limit: int | None = None) -> list[str]:
    lines = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            lines.append(line.rstrip("\r\n"))
    return lines


def index_parts(ldraw_dir: Path) -> list[list[str]]:
    rows = []
    for path in sorted((ldraw_dir / "parts").glob("*.dat")):
        lines = _read_lines(path, limit=40)
        if not lines or not lines[0].startswith("0 "):
            continue
        description = " ".join(lines[0][2:].split())
        category = keywords = part_type = ""
        for line in lines[1:]:
            words = line.split(maxsplit=2)
            if len(words) < 3 or words[0] != "0":
                continue
            if words[1] == "!CATEGORY":
                category = words[2].strip()
            elif words[1] == "!KEYWORDS":
                keywords = (keywords + ", " if keywords else "") + words[2].strip()
            elif words[1] == "!LDRAW_ORG":
                part_type = words[2].split()[0]
        if not category:
            # LDraw convention: the category is the description's first word.
            category = description.lstrip("~_=|").split(" ")[0]
        rows.append([path.name.lower(), description, category, keywords, part_type])
    return rows


def index_ref_models(ref_dir: Path) -> list[dict]:
    models = []
    for path in sorted(ref_dir.glob("*.mpd")) + sorted(ref_dir.glob("*.ldr")):
        submodels, parts = [], 0
        lines = _read_lines(path)
        for i, line in enumerate(lines):
            words = line.split()
            if len(words) >= 3 and words[0] == "0" and words[1] == "FILE":
                name = line.split("FILE", 1)[1].strip()
                description = ""
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if nxt.startswith("0 ") and not nxt[2:].lstrip().startswith(META_PREFIXES):
                    description = nxt[2:].strip()
                submodels.append({"name": name, "description": description})
            elif words and words[0] == "1" and line.lower().rstrip().endswith(".dat"):
                parts += 1
        models.append({"file": path.name, "parts": parts, "submodels": submodels})
    return models


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    ldraw_dir, ref_dir, out_dir = map(Path, argv[1:])
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = index_parts(ldraw_dir)
    (out_dir / "parts.json").write_text(json.dumps(parts, separators=(",", ":")))
    refs = index_ref_models(ref_dir)
    (out_dir / "ref-models.json").write_text(json.dumps(refs, separators=(",", ":")))
    print(f"indexed {len(parts)} parts, {len(refs)} reference models -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
