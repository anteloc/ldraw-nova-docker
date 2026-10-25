"""Kestrel Mk IV: ground-up rebuild of the Kestrel strike skiff (floating pose, >600 parts).

    .venv/bin/python output/kestrel4/generate.py
    ./ldraw-agent review output/kestrel4/kestrel4.plan.json --outdir output/kestrel4/review --contacts all --force

Axes: X width (starboard +X), -Z forward, -Y up. Y=0 is the keel underside. One "cell" = 20 LDU stud pitch;
cell (cx, cz) covers x in [20cx, 20cx+20), z in [20cz, 20cz+20). Plate layer k has its top at y = -8(k+1).
Reuses Halcyon's orient/seat helpers and its flank / nozzle / intake / cannon / cockpit recipes (attribution in
brief.md); the hull, plate packer, Technic spine, stepped nose, wings, nacelles and fins are new.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for parent in HERE.parents:
    if (parent / 'ldraw_tools').is_dir():
        sys.path.insert(0, str(parent))
        break
from ldraw_tools.builder import rotation  # noqa: E402

AUTHOR = 'Kestrel Mk IV generator (Claude), Halcyon-example helpers reused, for carlos.antelo'
DG, BK, YL, GLOW, GLASS, LG = 72, 0, 14, 43, 40, 71

PLATE = {(1, 1): '3024', (2, 1): '3023b', (3, 1): '3623', (4, 1): '3710', (6, 1): '3666', (8, 1): '3460',
         (10, 1): '4477', (2, 2): '3022', (3, 2): '3021', (4, 2): '3020', (6, 2): '3795', (8, 2): '3034'}
TILE = {(1, 1): '3070b', (2, 1): '3069b', (3, 1): '63864', (4, 1): '2431', (6, 1): '6636', (8, 1): '4162',
        (2, 2): '3068b', (3, 2): '26603', (4, 2): '87079'}
BRICK = {(1, 1): '3005', (2, 1): '3004', (3, 1): '3622', (4, 1): '3010', (6, 1): '3009', (8, 1): '3008',
         (2, 2): '3003', (3, 2): '3002', (4, 2): '3001'}
DIMS = {}
for _t in (PLATE, TILE, BRICK):
    for (l, s), ref in _t.items():
        DIMS[ref] = (l, s)
DIMS['30414'] = (4, 1)
DIMS['2412b'] = (2, 1)


def Ry(deg):
    return np.array(rotation('y', deg).rows, float)


def orient(up, along):
    x = np.array(along, float)
    y = -np.array(up, float)
    r = np.column_stack([x, y, np.cross(x, y)])
    assert np.allclose(r.T @ r, np.eye(3)) and np.isclose(np.linalg.det(r), 1)
    return r


def seat(r, socket, stud):
    return np.array(stud, float) - r @ np.array(socket, float)


def clean(v):
    out = float(round(float(v), 9))
    return 0.0 if out == 0 else out


class Section:
    def __init__(self, name, description):
        self.name, self.description, self.steps, self.n = name, description, [], 0

    def step(self):
        self.steps.append([])
        return self

    def add(self, id, ref, colour, at, r=None, purpose=None):
        ref = ref if ref.endswith(('.dat', '.ldr')) else ref + '.dat'
        e = dict(id=id, ref=ref, colour=colour, at=[clean(v) for v in at])
        if r is not None and not np.allclose(r, np.eye(3)):
            e['matrix'] = [[clean(v) for v in row] for row in np.asarray(r)]
        if purpose:
            e['purpose'] = purpose
        if not self.steps:
            self.step()
        self.steps[-1].append(e)
        self.n += 1
        return e

    def uid(self, p):
        self.n += 0
        return f'{p}-{sum(len(s) for s in self.steps)}'

    def rect(self, ref, colour, x0, x1, z0, z1, top, prefix='p', purpose=None):
        """Upright rectangular part covering cells [x0,x1) x [z0,z1) with its origin (body top) at y=top."""
        l, s = DIMS[ref]
        w, d = x1 - x0, z1 - z0
        if (w, d) == (l, s):
            r = None
        elif (w, d) == (s, l):
            r = Ry(90)
        else:
            raise ValueError(f'{ref} is {l}x{s}, not {w}x{d}')
        return self.add(self.uid(prefix), ref, colour, [(x0 + x1) * 10, top, (z0 + z1) * 10], r, purpose)

    def plan(self):
        return dict(name=self.name, description=self.description, steps=[s for s in self.steps if s])


def ytop(layer):
    return -8 * (layer + 1)


def pack(sec, cells, table, top, rng, axis='x', maxlen=6, p2=0.3, prefix='p', purpose=None, colour_of=None):
    """Greedy seeded packer: cover `cells` ({(cx,cz): colour}) with parts from `table` (keys (long, short))."""
    free = dict(cells)
    d1, d2 = ((1, 0), (0, 1)) if axis == 'x' else ((0, 1), (1, 0))
    keys = sorted(free, key=(lambda c: (c[1], c[0])) if axis == 'x' else (lambda c: (c[0], c[1])))
    lens1 = sorted(l for (l, s) in table if s == 1 and l <= maxlen)
    lens2 = sorted(l for (l, s) in table if s == 2 and l <= maxlen)
    for c in keys:
        if c not in free:
            continue
        col = free[c]
        n1, p = 0, c
        while n1 < maxlen and free.get(p) == col:
            n1 += 1
            p = (p[0] + d1[0], p[1] + d1[1])
        cand = [l for l in lens1 if l <= n1]
        l = rng.choice(cand[-2:]) if len(cand) > 1 else cand[0]
        width = 1
        if rng.random() < p2:
            for l2 in [x for x in lens2 if x <= n1][::-1]:
                if all(free.get((c[0] + i * d1[0] + d2[0], c[1] + i * d1[1] + d2[1])) == col for i in range(l2)):
                    l, width = l2, 2
                    break
        if axis == 'x':
            x0, x1, z0, z1 = c[0], c[0] + l, c[1], c[1] + width
        else:
            x0, x1, z0, z1 = c[0], c[0] + width, c[1], c[1] + l
        for x in range(x0, x1):
            for z in range(z0, z1):
                del free[(x, z)]
        sec.rect(table[(l, width)], col, x0, x1, z0, z1, top, prefix, purpose)


def mir(cells):
    return {(-1 - cx, cz): v for (cx, cz), v in cells.items()}


# ----------------------------------------------------------------------------------------------- layout
ZA, ZB = -18, 17            # nose tip row, tail row
CANNON_CELL = (9, 6)
WIN = (0, 6)                # hull-side window rows (inclusive): Technic spine visible
NAC = [(cx, z) for cx in range(4, 8) for z in range(7, 18)]          # starboard nacelle footprint


def hw(z):
    return 1 if z <= -17 else 2 if z <= -13 else 3 if z <= -9 else 4


def nose_n(z):
    """Layers (height) of the nose column at row z; the last row of every step is a cheese slope."""
    return {-18: 2, -17: 2, -16: 3, -15: 3, -14: 4, -13: 4, -12: 5, -11: 5, -10: 6, -9: 6}[z]


FUS = {(cx, z) for z in range(ZA, ZB + 1) for cx in range(-hw(z), hw(z))}


def wing_e(z):
    return 8 + (2 * (z - 3)) // 3     # exclusive outer bound at row z (z >= 5)


def wing_cells(trim):
    return {(cx, z) for z in range(5, 18) for cx in range(8, wing_e(z) - trim)}


# ------------------------------------------------------------------------------------------- hull modules
def keel():
    s = Section('kestrel4-keel.ldr', 'Keel: two plate layers spanning hull, nacelle roots and wings, bonded across seams')
    rng = random.Random(11)
    nac = set(NAC) | set(mir({c: 0 for c in NAC}))
    w0 = wing_cells(0)
    w0 |= set(mir({c: 0 for c in w0}))
    l0 = {}
    for c in FUS:
        l0[c] = BK
    for c in nac | w0:
        l0[c] = DG
    s.step()
    pack(s, l0, PLATE, ytop(0), rng, 'z', maxlen=8, p2=0.35, prefix='k0', purpose='Keel layer 0')
    w1 = wing_cells(0)
    w1 |= set(mir({c: 0 for c in w1}))
    l1 = {}
    for c in FUS:
        if c[1] >= -16:
            l1[c] = BK
    for c in nac:
        l1[c] = BK
    for c in w1:
        l1[c] = DG
    s.step()
    pack(s, l1, PLATE, ytop(1), rng, 'x', maxlen=8, p2=0.35, prefix='k1', purpose='Keel layer 1')
    return s


def nose():
    s = Section('kestrel4-nose.ldr', 'Needle nose: one-plate steps, each ending in a row of cheese slopes')
    rng = random.Random(5)
    # tip: tile on the L0 plates at z -18 (hull L1 is absent for z < -16)
    s.step()
    tip = {(cx, -18): DG for cx in range(-1, 1)}
    pack(s, tip, TILE, ytop(1), rng, 'x', maxlen=2, p2=0, prefix='tip', purpose='Nose tip tile')
    for i, z in enumerate((-17, -15, -13, -11, -9)):
        for cx in range(-hw(z), hw(z)):
            n = nose_n(z)
            col = YL if cx in (-1, 0) else DG
            s.add(f'slope-{i}-{cx}', '54200', col, [cx * 20 + 10, ytop(n - 2), z * 20 + 10], None, 'Cheese slope closes the step')
    # step bodies: layers 2..n-2 plates, layer n-1 tile (except slope rows)
    for layer in range(2, 6):
        s.step()
        cells = {}
        for z in range(-16, -8):
            n = nose_n(z)
            if layer <= n - 2:
                for cx in range(-hw(z), hw(z)):
                    cells[(cx, z)] = DG
        if cells:
            pack(s, cells, PLATE, ytop(layer), rng, 'x' if layer % 2 else 'z', maxlen=4, p2=0.2, prefix=f'n{layer}',
                 purpose='Nose plate layer')
    s.step()
    tiles = {}
    for z in range(-16, -9):
        n = nose_n(z)
        if z in (-15, -13, -11, -9):
            continue
        for cx in range(-hw(z), hw(z)):
            tiles[(cx, z)] = YL if cx in (-1, 0) else DG
    # tiles at different heights: group by height
    by_n = {}
    for (cx, z), col in tiles.items():
        by_n.setdefault(nose_n(z), {})[(cx, z)] = col
    for n, cells in by_n.items():
        pack(s, cells, TILE, ytop(n - 1), rng, 'x', maxlen=4, p2=0, prefix=f'nt{n}', purpose='Nose top tile')
    return s


# ------------------------------------------------------------------------------------------------ helpers
SP_TOP = ytop(4)             # top of the brick course on layers 2-4 (y = -40)
NAC_TOP = ytop(7)            # top of the nacelle brick course on layers 5-7 (y = -64)
FACE_YAW = {(0, 0, -1): 0, (1, 0, 0): -90, (0, 0, 1): 180, (-1, 0, 0): 90}


def side_stud(sec, id, colour, face, cx, cz, top, purpose=None):
    """30414 with its four side studs facing `face`; (cx, cz) is the brick centre in LDU."""
    return sec.add(id, '30414', colour, [cx, top, cz], Ry(FACE_YAW[tuple(face)]), purpose or f'side studs face {face}')


def deck_colour(cx, z):
    if cx in (-1, 0) and 7 <= z <= 17:
        return BK
    if cx in (-3, 2) and -8 <= z <= 6:
        return YL
    if cx in (-4, 3) and z >= 8:
        return BK
    return DG


def body():
    s = Section('kestrel4-body.ldr', 'Hull: Technic spine, wall bricks, side-stud mounts, deck, cockpit floor and interior')
    rng = random.Random(21)
    s.step()
    for k in range(6):
        z0 = -8 + 4 * k
        zc = (z0 + 2) * 20
        for cx in (-1, 0):
            s.add(f'spine-{k}-{cx}', '3701', BK, [cx * 20 + 10, SP_TOP, zc], Ry(90), 'Technic spine brick, holes across the hull')
        for dz in (-20, 0, 20):
            col = YL if WIN[0] <= z0 <= WIN[1] else BK
            s.add(f'pin-{k}-{dz}', '4459', col, [0, SP_TOP + 10, zc + dz], None, 'Friction pin locking the spine pair')
    s.step()
    reserved = set()
    for cx0, face in ((3, (1, 0, 0)), (-4, (-1, 0, 0))):
        for z0 in (-8, -4):
            side_stud(s, f'flank-mount-{cx0}-{z0}', DG, face, cx0 * 20 + 10, (z0 + 2) * 20, SP_TOP, 'Flank panel mount')
            reserved |= {(cx0, z) for z in range(z0, z0 + 4)}
    for cx0 in (-4, 0):
        side_stud(s, f'aft-mount-{cx0}', DG, (0, 0, 1), (cx0 + 2) * 20, 17 * 20 + 10, SP_TOP, 'Aft cap mount')
        reserved |= {(cx0 + i, 17) for i in range(4)}
    walls = {}
    for z in range(-8, 18):
        for cx in range(-4, 4):
            if cx in (-1, 0) and z <= 15:
                continue
            if cx not in (-1, 0) and WIN[0] <= z <= WIN[1]:
                continue
            if (cx, z) in reserved:
                continue
            walls[(cx, z)] = DG
    pack(s, walls, BRICK, SP_TOP, rng, 'z', maxlen=6, p2=0.3, prefix='wall', purpose='Wall brick course')
    s.step()
    deck = {(cx, z): DG for (cx, z) in FUS if z >= -8}
    pack(s, deck, PLATE, ytop(5), rng, 'z', maxlen=8, p2=0.35, prefix='deck', purpose='Deck plate layer')
    s.step()
    ridge = {(cx, z): BK for cx in (-1, 0) for z in range(7, 16)}
    grilles = [(a, a + 2, z) for z in (10, 12, 14) for a in (1, -3)]
    gcells = {(x, z) for a, b, z in grilles for x in range(a, b)}
    tiles = {(cx, z): deck_colour(cx, z) for (cx, z) in FUS
             if z >= -8 and not (-2 <= cx <= 1 and -7 <= z <= -1) and (cx, z) not in ridge and (cx, z) not in gcells}
    pack(s, tiles, TILE, ytop(6), rng, 'x', maxlen=4, p2=0.25, prefix='dt', purpose='Deck tile')
    for a, b, z in grilles:
        s.rect('2412b', LG, a, b, z, z + 1, ytop(6), 'grille', 'Deck grille')
    pack(s, ridge, PLATE, ytop(6), rng, 'z', maxlen=8, p2=0, prefix='rp', purpose='Ridge base plate')
    for cx in (-1, 0):
        s.add(f'ridge-slope-{cx}', '54200', YL, [cx * 20 + 10, ytop(6), 7 * 20 + 10], None, 'Ridge ramp')
    s.step()
    for k, z0 in enumerate((8, 12)):
        zc = (z0 + 2) * 20
        for cx in (-1, 0):
            s.add(f'ridge-{k}-{cx}', '3701', BK, [cx * 20 + 10, ytop(9), zc], Ry(90), 'Dorsal Technic ridge brick')
        for dz in (-20, 0, 20):
            s.add(f'ridge-pin-{k}-{dz}', '4459', YL, [0, ytop(9) + 10, zc + dz], None, 'Ridge pin')
        s.rect('87079', YL if k == 0 else DG, -1, 1, z0, z0 + 4, ytop(10), 'ridge-tile', 'Ridge cap tile')
    s.step()
    t = ytop(6)
    for side, (a, b) in (('s', (1, 2)), ('p', (-2, -1))):
        s.rect('3069b', LG, a, b, -7, -5, t, 'sill', 'Cabin sill')
        s.rect('3069b', LG, a, b, -4, -2, t, 'side', 'Cabin side')
    s.rect('2431', YL, -2, 2, -5, -4, t, 'console', 'Instrument console')
    s.rect('3068b', BK, -1, 1, -4, -2, t, 'seat', 'Seat')
    s.rect('87079', BK, -2, 2, -2, 0, t, 'aft', 'Cabin aft')
    s.add('canopy', '30384', GLASS, [0, ytop(5), -90], None, 'Rounded canopy on the four floor studs')
    return s


def wing(side):
    sx = 1 if side == 's' else -1
    f = (lambda c: c) if sx == 1 else (lambda c: (-1 - c[0], c[1]))
    s = Section(f'kestrel4-wing-{side}.ldr', f'{side} wing: tiled top layer, raised inboard deck, yellow leading edge, cannon mount')
    rng = random.Random(31 if sx == 1 else 32)
    T0 = wing_cells(0)
    U = {c for c in T0 if c[1] >= 10 and c[0] < wing_e(c[1]) - 4}
    cannon = CANNON_CELL
    tiles = {}
    for c in T0 - U - {cannon}:
        lead = (c[0], c[1] - 1) not in T0
        second = (c[0], c[1] - 2) not in T0
        tiles[f(c)] = YL if lead else BK if (c[1] >= 16 or second) else DG
    s.step()
    pack(s, {f(c): DG for c in U | {cannon}}, PLATE, ytop(2), rng, 'x', maxlen=4, p2=0.3, prefix='wu', purpose='Wing inboard deck plate')
    pack(s, tiles, TILE, ytop(2), rng, 'x', maxlen=4, p2=0.3, prefix='wt', purpose='Wing top tile')
    s.step()
    ut = {f(c): (YL if (c[0], c[1] - 1) not in U else BK if c[1] == 17 else DG) for c in U}
    pack(s, ut, TILE, ytop(3), rng, 'z', maxlen=4, p2=0.3, prefix='wd', purpose='Raised wing deck tile')
    cx, z = f(cannon)
    s.add('cannon-mount', '87087', DG, [cx * 20 + 10, ytop(5), z * 20 + 10], None, 'Side stud faces forward for the cannon')
    return s


def nacelle(side):
    sx = 1 if side == 's' else -1
    f = (lambda c: c) if sx == 1 else (lambda c: (-1 - c[0], c[1]))
    s = Section(f'kestrel4-nacelle-{side}.ldr', f'{side} engine nacelle: plate base, brick course with side studs, tiles, fin')
    rng = random.Random(41 if sx == 1 else 42)
    for layer in (2, 3, 4):
        s.step()
        pack(s, {f(c): DG for c in NAC}, PLATE, ytop(layer), rng, 'x' if layer % 2 else 'z', maxlen=6, p2=0.3,
             prefix=f'np{layer}', purpose='Nacelle plate layer')
    s.step()
    bx = 120 * sx
    side_stud(s, 'front-mount', DG, (0, 0, -1), bx, 150, NAC_TOP, 'Intake mount')
    side_stud(s, 'rear-mount', DG, (0, 0, 1), bx, 350, NAC_TOP, 'Nozzle mount')
    for i, z0 in enumerate((9, 13)):
        side_stud(s, f'pod-mount-{i}', DG, (sx, 0, 0), 150 * sx, (z0 + 2) * 20, NAC_TOP, 'Outer panel mount')
    res = {(c[0], 7) for c in NAC} | {(c[0], 17) for c in NAC} | {(7, z) for z in range(9, 17)}
    cells = {f(c): DG for c in NAC if c not in res}
    pack(s, cells, BRICK, NAC_TOP, rng, 'z', maxlen=4, p2=0.3, prefix='nb', purpose='Nacelle brick course')
    s.step()
    fin = {(6, z) for z in range(10, 17)}
    tiles = {}
    for c in NAC:
        if c in fin:
            continue
        col = YL if c[0] in (5, 6) and 9 <= c[1] <= 15 else BK if c[1] >= 16 else DG
        tiles[f(c)] = col
    pack(s, tiles, TILE, ytop(8), rng, 'z', maxlen=4, p2=0.25, prefix='nt', purpose='Nacelle top tile')
    pack(s, {f(c): DG for c in fin}, PLATE, ytop(8), rng, 'z', maxlen=4, p2=0, prefix='fb', purpose='Fin base plate')
    for j in range(4):
        s.step()
        z0 = 10 + j
        base = 9 + 3 * j
        col = YL if j == 2 else DG
        pack(s, {f((6, z)): col for z in range(z0, 17)}, BRICK, ytop(base + 2), rng, 'z', maxlen=4, p2=0,
             prefix=f'fin{j}', purpose='Swept fin course')
        cx, z = f((6, z0))
        s.add(f'fin-slope-{j}', '54200', DG if j != 2 else YL, [cx * 20 + 10, ytop(base + 2), z * 20 + 10], None, 'Leading-edge slope')
    s.step()
    s.rect('2431', YL, *(lambda c: (c[0], c[0] + 1))(f((6, 13))), 13, 17, ytop(21), 'fcap', 'Fin cap')
    return s


FLANK_R = {'s': orient(up=(1, 0, 0), along=(0, 0, 1)), 'p': orient(up=(-1, 0, 0), along=(0, 0, 1))}
FWD_R = orient(up=(0, 0, -1), along=(1, 0, 0))
AFT_R = orient(up=(0, 0, 1), along=(1, 0, 0))


def flank(side):
    sx = 1 if side == 's' else -1
    s = Section(f'kestrel4-flank-{side}.ldr', f'{side} flank panel built flat and turned onto side studs')
    up = 10 * sx
    s.step().add('base', '3034', DG, [0, -8, 0], None, 'Two-row base plate on the side studs')
    s.step()
    s.add('stripe', '4162', YL, [0, -16, up], None, 'Yellow stripe')
    s.add('lower-a', '2431', BK, [-40, -16, -up], None, 'Lower tile')
    s.add('lower-b', '2431', DG, [40, -16, -up], None, 'Lower tile')
    return s


def pod_panel(side):
    s = Section(f'kestrel4-pod-panel-{side}.ldr', f'{side} nacelle outer stripe')
    s.step().add('base', '3460', DG, [0, -8, 0], None, 'One-row base on side studs')
    s.step().add('stripe', '4162', YL, [0, -16, 0], None, 'Stripe')
    return s


def intake():
    s = Section('kestrel4-intake.ldr', 'Intake ring, hub and spinner built along their own axis')
    s.step().add('ring', '60474', BK, [0, 0, 0], None, 'Round 4x4 on four forward studs')
    s.step().add('hub', '3941', DG, [0, -24, 0], None, 'Hub')
    s.step().add('spinner', '98100', YL, [0, -48, 0], None, 'Spinner')
    return s


def nozzle():
    s = Section('kestrel4-exhaust.ldr', 'Exhaust nozzle: ring, jumper, bell and glowing core')
    s.step().add('ring', '60474', BK, [0, 0, 0], None, 'Ring on four aft studs')
    s.step().add('jumper', '87580', BK, [0, -8, 0], None, 'Centre stud')
    s.step().add('bell', '3960', DG, [0, -24, 0], None, 'Bell')
    s.step().add('core', '4740', GLOW, [0, -32, 0], None, 'Glowing core')
    return s


def aft_cap():
    s = Section('kestrel4-aft-cap.ldr', 'Aft cap: dark panel with grille and glowing vents')
    s.step().add('panel', '3020', BK, [0, 0, 0], None, 'On aft-facing studs')
    s.step()
    s.add('vent-a', '98138', GLOW, [30, -8, -10], None, 'Vent')
    s.add('vent-b', '98138', GLOW, [-30, -8, -10], None, 'Vent')
    s.add('grille', '2412b', LG, [0, -8, -10], None, 'Grille')
    s.add('lower', '2431', DG, [0, -8, 10], None, 'Lower tile')
    return s


def cannon():
    s = Section('kestrel4-cannon.ldr', 'Wing-root cannon stacked along its own axis')
    for i, (ref, col, y) in enumerate((('85861', BK, 0), ('3062b', DG, -24), ('85861', YL, -32),
                                       ('3062b', DG, -56), ('98138', BK, -64))):
        s.step().add(f'barrel-{i}', ref, col, [0, y, 0])
    return s


def belly():
    s = Section('kestrel4-belly.ldr', 'Ventral Technic keel hanging under the hull: studs up into the keel underside')
    rng = random.Random(51)
    s.step()
    for k in range(4):
        z0 = -4 + 4 * k
        zc = (z0 + 2) * 20
        for cx in (-1, 0):
            s.add(f'bspine-{k}-{cx}', '3701', BK, [cx * 20 + 10, 0, zc], Ry(90), 'Ventral Technic brick')
        for dz in (-20, 0, 20):
            s.add(f'bpin-{k}-{dz}', '4459', YL, [0, 10, zc + dz], None, 'Ventral pin')
    caps = {(cx, z): BK for cx in (-2, 1) for z in list(range(-4, 0)) + list(range(8, 12))}
    pack(s, caps, BRICK, 0, rng, 'z', maxlen=4, p2=0, prefix='bw', purpose='Ventral end brick')
    s.step()
    under = {(cx, z): DG for cx in range(-2, 2) for z in range(-4, 12)}
    pack(s, under, PLATE, 24, rng, 'x', maxlen=6, p2=0.3, prefix='bu', purpose='Ventral plate layer')
    return s


def build():
    mods = [keel(), nose(), body(), belly(), wing('s'), wing('p'), nacelle('s'), nacelle('p'), flank('s'), flank('p'),
            pod_panel('s'), pod_panel('p'), intake(), nozzle(), aft_cap(), cannon()]
    root = Section('kestrel4.ldr', 'Kestrel Mk IV strike skiff, floating pose')
    for name in ('keel', 'nose', 'body', 'belly'):
        root.step().add(name, f'kestrel4-{name}.ldr', 16, [0, 0, 0])
    root.step()
    for side in 'sp':
        root.add(f'wing-{side}', f'kestrel4-wing-{side}.ldr', 16, [0, 0, 0])
        root.add(f'nacelle-{side}', f'kestrel4-nacelle-{side}.ldr', 16, [0, 0, 0])
    root.step()
    for side, sx in (('s', 1), ('p', -1)):
        root.add(f'flank-{side}', f'kestrel4-flank-{side}.ldr', 16,
                 seat(FLANK_R[side], [-70, 0, 10 * sx], [80 * sx, SP_TOP + 10, -150]), FLANK_R[side])
        root.add(f'pod-panel-{side}', f'kestrel4-pod-panel-{side}.ldr', 16,
                 seat(FLANK_R[side], [-70, 0, 0], [160 * sx, NAC_TOP + 10, 190]), FLANK_R[side])
    root.step()
    for side, sx in (('s', 1), ('p', -1)):
        bx = 120 * sx
        root.add(f'intake-{side}', 'kestrel4-intake.ldr', 16, seat(FWD_R, [10, 8, 10], [bx + 10, NAC_TOP + 10, 140]), FWD_R)
        root.add(f'exhaust-{side}', 'kestrel4-exhaust.ldr', 16, seat(AFT_R, [10, 8, -10], [bx + 10, NAC_TOP + 10, 360]), AFT_R)
        root.add(f'cannon-{side}', 'kestrel4-cannon.ldr', 16, seat(FWD_R, [0, 8, 0], [190 * sx, ytop(5) + 10, 120]), FWD_R)
        root.add(f'aft-cap-{side}', 'kestrel4-aft-cap.ldr', 16,
                 seat(AFT_R, [10, 8, -10], [40 * sx + 10, SP_TOP + 10, 360]), AFT_R)
    return dict(version=1, author=AUTHOR, sections=[root.plan()] + [m.plan() for m in mods])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=HERE / 'kestrel4.plan.json')
    a = ap.parse_args()
    plan = build()
    a.output.write_text(json.dumps(plan, indent=1) + '\n')
    n = sum(len(st) for sec in plan['sections'] for st in sec['steps'])
    print(a.output, 'placements incl. module refs:', n)


if __name__ == '__main__':
    main()
