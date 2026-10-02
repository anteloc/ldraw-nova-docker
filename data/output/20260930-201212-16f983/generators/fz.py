"""Fiamma V8 helper: measured part bounds, connector frames and donor data (read-only toolkit use).

All geometry comes from the installed library through ldraw_tools.common.get_parts() / pyldraw3.
Car frame: X across (+X = driver side), -Z forward, Y=0 road, negative Y up, Z=0 front-axle centre.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

sys.path.insert(0, '.')
from ldraw_tools.common import get_parts, normalized  # noqa: E402

PARTS = get_parts()
OUT = Path('output')
DONOR_SHIFT = np.array([0, 20, 60])  # 42039 world -> car frame


def code(ref):
    return normalized(ref).removesuffix('.dat')


def desc(ref):
    return PARTS.by_code.get(code(ref), '')


@lru_cache(maxsize=None)
def geom(ref):
    return PARTS.geometry(code(ref))


def bounds(ref):
    b = geom(ref).bounds
    return np.array([b.min.x, b.min.y, b.min.z], float), np.array([b.max.x, b.max.y, b.max.z], float)


def world_aabb(ref, M, t):
    lo, hi = bounds(ref)
    c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    w = (np.asarray(M) @ c.T).T + np.asarray(t)
    return w.min(0), w.max(0)


def connectors(ref):
    """Local connector list: dict(kind, pos, dir) from pyldraw3 connection inference + shadow."""
    out = []
    for c in geom(ref).connections:
        d = c.to_dict() if hasattr(c, 'to_dict') else dict(c.__dict__)
        out.append(d)
    return out


def load_donor():
    rows = json.load(open(OUT / 'phase3/donor-42039-carframe.json'))
    for r in rows:
        r['M'] = np.array(r['mat'])
        r['t'] = np.array(r['pos'])
    return rows


def rot(axis, deg):
    a = np.radians(deg)
    c, s = round(np.cos(a), 12), round(np.sin(a), 12)
    if axis == 'x':
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'y':
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def overlaps(a, b, tol=0.5):
    return bool(np.all(a[0] < b[1] - tol) and np.all(b[0] < a[1] - tol))
