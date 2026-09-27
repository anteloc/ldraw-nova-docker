"""Build the parts index the agent tools use (find_parts). Run once at image build time:

    python3 build_index.py <ldraw-dir> <out-dir>

Writes:
  parts.json       [[id, description, category, keywords, type], ...] for parts/*.dat
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

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


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    ldraw_dir, out_dir = map(Path, argv[1:])
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = index_parts(ldraw_dir)
    (out_dir / "parts.json").write_text(json.dumps(parts, separators=(",", ":")))
    print(f"indexed {len(parts)} parts -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
