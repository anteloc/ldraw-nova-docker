"""Editable sculpture artifacts bound to the exact checked model revision."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import settings


def siblings(model: Path) -> tuple[Path, Path]:
    return model.with_suffix('.repaired.voxels.json'), model.with_suffix('.sculpture.json')


def validate_rows(rows: object) -> None:
    if not isinstance(rows, list) or not 1 <= len(rows) <= 65536:
        raise ValueError('Keep between 1 and 65,536 cells in the sculpture.')
    cells = set()
    bounds = [[100001, -100001] for _ in range(3)]
    for row in rows:
        if not isinstance(row, list) or len(row) != 4 or any(type(v) is not int for v in row):
            raise ValueError('Each cell must contain integer x, y, z and LDraw colour.')
        if any(abs(v) > 100000 for v in row[:3]) or not 0 <= row[3] <= 511 or row[3] in (16, 24):
            raise ValueError('Use bounded coordinates and an explicit LDraw colour.')
        key = tuple(row[:3])
        if key in cells:
            raise ValueError('Each cell position must be unique.')
        cells.add(key)
        for i in range(3):
            bounds[i] = [min(bounds[i][0], row[i]), max(bounds[i][1], row[i])]
    sizes = [hi - lo + 1 for lo, hi in bounds]
    if max(sizes) > 96 or sizes[0] * sizes[1] * sizes[2] > 262144:
        raise ValueError('Keep the sculpture within 96 cells per axis and 262,144 grid cells.')


def read(model: Path) -> dict | None:
    voxels, marker = siblings(model)
    try:
        if any(p.is_symlink() or not p.is_file() for p in (model, voxels, marker)):
            return None
        if model.stat().st_size > 32 * 1024 * 1024 or voxels.stat().st_size > 8 * 1024 * 1024 or marker.stat().st_size > 1024:
            return None
        meta = json.loads(marker.read_text())
        if (meta.get('version') != 1 or meta.get('model_sha256') != hashlib.sha256(model.read_bytes()).hexdigest()
                or meta.get('voxel_sha256') != hashlib.sha256(voxels.read_bytes()).hexdigest()):
            return None
        data = json.loads(voxels.read_text())
        validate_rows(data.get('voxels'))
        return {**data, 'revision': meta['model_sha256']}
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def palette() -> list[dict]:
    colours = []
    config = settings.LDRAW_DIR / 'LDConfig.ldr'
    if config.is_file():
        for line in config.read_text(errors='replace').splitlines():
            match = re.match(r'0\s+!COLOUR\s+(\S+)\s+CODE\s+(\d+)\s+VALUE\s+(#[\dA-Fa-f]{6})', line)
            if match and 0 <= int(match[2]) <= 511 and int(match[2]) not in (16, 24):
                colours.append({'code': int(match[2]), 'name': match[1].replace('_', ' '), 'hex': match[3]})
    return colours
