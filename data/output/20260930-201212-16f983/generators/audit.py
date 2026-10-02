"""Audit the generated plan: inter-module pin joins (heuristic) and OBB clashes around chosen parts.

Usage: .venv/bin/python output/generators/audit.py [module-substring ...]
All modules are placed at identity in the main section, so section-local coordinates are car-frame coordinates.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, 'output/generators')
import fz  # noqa: E402
import joins  # noqa: E402


def load(plan='output/fiamma.plan.json', skip=('fiamma-v8.ldr',)):
    P = json.load(open(plan))
    rows = []
    for sec in P['sections']:
        if sec['name'] in skip:
            continue
        for st in sec['steps']:
            for e in st:
                if e['ref'].endswith('.ldr'):
                    continue
                rows.append(dict(ref=e['ref'], colour=e['colour'], M=np.array(e['matrix']), t=np.array(e['at']),
                                 mod=sec['name'], id=e['id'], desc=fz.desc(e['ref'])))
    return rows


def obb_overlap(a, b, shrink=1.0):
    """Separating-axis test on local bounds shrunk by `shrink` LDU (penetration > shrink)."""
    def box(r):
        lo, hi = fz.bounds(r['ref'])
        c = (lo + hi) / 2
        return r['t'] + r['M'] @ c, r['M'], np.maximum((hi - lo) / 2 - shrink, 0.01)
    ca, Ra, ha = box(a)
    cb, Rb, hb = box(b)
    d = cb - ca
    axes = [Ra[:, i] for i in range(3)] + [Rb[:, i] for i in range(3)]
    for i in range(3):
        for j in range(3):
            v = np.cross(Ra[:, i], Rb[:, j])
            if np.linalg.norm(v) > 1e-6:
                axes.append(v / np.linalg.norm(v))
    for ax in axes:
        ra = sum(ha[k] * abs(Ra[:, k] @ ax) for k in range(3))
        rb = sum(hb[k] * abs(Rb[:, k] @ ax) for k in range(3))
        if abs(d @ ax) > ra + rb:
            return False
    return True


def module_joins(rows):
    J = joins.joins(rows)
    links = defaultdict(list)
    for i, hit in J:
        mods = {rows[j]['mod'] for j in hit} | {rows[i]['mod']}
        if len(mods) > 1:
            links[tuple(sorted(mods))].append((rows[i]['id'], [round(v) for v in rows[i]['t']]))
    return links


if __name__ == '__main__':
    rows = load()
    links = module_joins(rows)
    for k, v in sorted(links.items()):
        print('JOIN', ' <-> '.join(m.replace('.ldr', '') for m in k), len(v), v[:4])
    focus = sys.argv[1:] or ['m3-gearbox']
    tgt = [r for r in rows if any(f in r['mod'] for f in focus)]
    boxes = {id(r): fz.world_aabb(r['ref'], r['M'], r['t']) for r in rows}
    for a in tgt:
        for b in rows:
            if b is a or (b['mod'] == a['mod'] and b['id'] <= a['id']):
                continue
            if not fz.overlaps(boxes[id(a)], boxes[id(b)]):
                continue
            if joins.is_male(a['ref']) or joins.is_male(b['ref']):
                continue
            if obb_overlap(a, b, 1.0):
                print('CLASH?', a['mod'][3:-4], a['id'], '<->', b['mod'][3:-4], b['id'], [round(v) for v in b['t']])
