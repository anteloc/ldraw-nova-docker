"""Structural join map: which parts each pin/axle passes through (oriented-box containment along its axis).

Heuristic evidence only (not connector certification). Male = pins, axles, axle-pins, long pins (long axis = local X).
"""
from __future__ import annotations

import re

import numpy as np

import fz

MALE = re.compile(r'^Technic (Pin|Axle)(?! Joiner| Connector)|Technic Axle Pin', re.I)
NOT_MALE = re.compile(r'Joiner|Connector|Hub|Bush|Towball|Cross Block', re.I)


def is_male(ref):
    d = fz.desc(ref)
    return bool(MALE.search(d)) and not NOT_MALE.search(d)


def segment(r):
    lo, hi = fz.bounds(r['ref'])
    M, t = r['M'], r['t']
    return t + M @ np.array([lo[0] + 1, 0, 0]), t + M @ np.array([hi[0] - 1, 0, 0])


def inside(r, p, margin=0.8):
    lo, hi = fz.bounds(r['ref'])
    q = r['M'].T @ (p - r['t'])
    return bool(np.all(q > lo + margin) and np.all(q < hi - margin))


def joins(rows, step=4.0):
    """Return list of (male_index, [part indices pierced]) using world AABB prefilter."""
    boxes = [fz.world_aabb(r['ref'], r['M'], r['t']) for r in rows]
    out = []
    for i, r in enumerate(rows):
        if not is_male(r['ref']):
            continue
        a, b = segment(r)
        n = max(2, int(np.linalg.norm(b - a) / step) + 1)
        pts = [a + (b - a) * k / (n - 1) for k in range(n)]
        lo = np.minimum(a, b) - 1
        hi = np.maximum(a, b) + 1
        hit = []
        for j, (blo, bhi) in enumerate(boxes):
            if j == i or np.any(blo > hi) or np.any(bhi < lo):
                continue
            if is_male(rows[j]['ref']):
                continue
            if any(inside(rows[j], p) for p in pts):
                hit.append(j)
        out.append((i, hit))
    return out
