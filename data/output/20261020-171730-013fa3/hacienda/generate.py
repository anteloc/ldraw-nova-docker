#!/usr/bin/env python3
"""Hacienda del Sol - procedural plan generator.  Run: .venv/bin/python output/hacienda/generate.py
Writes output/hacienda/hacienda.plan.json (editable source) then build with ./ldraw-agent."""
import json, os, random
from collections import defaultdict

random.seed(7)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hacienda.plan.json")

# ---------------------------------------------------------------- palette
WALL, PLINTH, WHITE, ROOF, WOOD, BLACK = 191, 25, 15, 320, 70, 0
GREEN, DGREEN, MAGENTA, PINK, RED, BLUE, YELLOW = 2, 288, 5, 13, 4, 1, 14
TRBLUE, TRYEL, GOLD, DTAN, TAN, DBG, LBG = 43, 36, 297, 28, 19, 72, 71

steps = []
cur = None
used = defaultdict(int)


def step():
    global cur
    cur = []
    steps.append(cur)


def put(ref, colour, x, y, z, yaw=0, tag="p"):
    used[tag] += 1
    d = {"id": f"{tag}-{used[tag]}", "ref": ref if ref.endswith(".dat") else ref + ".dat",
         "colour": colour, "at": [round(x, 3), round(y, 3), round(z, 3)]}
    if yaw:
        d["yaw"] = yaw
    cur.append(d)


# ---------------------------------------------------------------- coordinates
BX, BZ = 8, 12          # building origin (u=0,v=0) in base studs
Y0 = -8                 # floor top (plate on baseplate)
H = 6                   # wall courses


def cx(gx): return (gx - 32) * 20 + 10
def cz(gz): return (gz - 32) * 20 + 10
def U(u): return cx(u + BX)
def V(v): return cz(v + BZ)
def ytop(course, floor=Y0, h=1): return floor - 24 * (course + h)   # origin of brick whose body is h courses


# ---------------------------------------------------------------- rectangle packers
BRICKS = [(2, 8, "3007"), (2, 6, "2456"), (2, 4, "3001"), (2, 3, "3002"), (2, 2, "3003"),
          (1, 8, "3008"), (1, 6, "3009"), (1, 4, "3010"), (1, 3, "3622"), (1, 2, "3004"), (1, 1, "3005")]
PLATES = [(4, 8, "3035"), (4, 6, "3032"), (4, 4, "3031"), (2, 8, "3034"), (2, 6, "3795"), (2, 4, "3020"),
          (2, 3, "3021"), (2, 2, "3022"), (1, 8, "3460"), (1, 6, "3666"), (1, 4, "3710"), (1, 3, "3623"),
          (1, 2, "3023b"), (1, 1, "3024")]
TILES = [(2, 4, "87079"), (2, 2, "3068b"), (1, 8, "4162"), (1, 6, "6636"), (1, 4, "2431"), (1, 2, "3069b"), (1, 1, "3070b")]


def pack(cells, sizes):
    """Greedy rectangles. returns [(u0,v0,wu,wv,ref)] where wu extent in u, wv extent in v."""
    cells = set(cells)
    out = []
    order = sorted(cells, key=lambda c: (c[1], c[0]))
    cand = []
    for w, l, ref in sizes:
        cand.append((w * l, w, l, ref))
    cand.sort(key=lambda t: -t[0])
    for (u, v) in order:
        if (u, v) not in cells:
            continue
        done = False
        for area, w, l, ref in cand:
            shapes = [(l, w)] if w == l else [(l, w), (w, l)]
            for (wu, wv) in shapes:
                if all((u + i, v + j) in cells for i in range(wu) for j in range(wv)):
                    for i in range(wu):
                        for j in range(wv):
                            cells.discard((u + i, v + j))
                    out.append((u, v, wu, wv, ref))
                    done = True
                    break
            if done:
                break
    return out


def place_rects(rects, colour, y, tag, to_world=None):
    """to_world maps (u,v)->(x,z) of cell centre."""
    tw = to_world or (lambda u, v: (U(u), V(v)))
    for (u, v, wu, wv, ref) in rects:
        x0, z0 = tw(u, v)
        x1, z1 = tw(u + wu - 1, v + wv - 1)
        yaw = 90 if wv > wu else 0
        put(ref, colour, (x0 + x1) / 2, y, (z0 + z1) / 2, yaw, tag)


# run-based brick splitting (staggered)
def split_run(L):
    best = {0: (0, [])}
    sizes = [8, 6, 4, 3, 2, 1]
    wt = {8: 1, 6: 1, 4: 1, 3: 1, 2: 1, 1: 3}
    for n in range(1, L + 1):
        c = None
        for s in sizes:
            if n - s >= 0 and (n - s) in best:
                cost = best[n - s][0] + wt[s]
                if c is None or cost < c[0]:
                    c = (cost, best[n - s][1] + [s])
        best[n] = c
    return best[L][1]


BR = {8: "3008", 6: "3009", 4: "3010", 3: "3622", 2: "3004", 1: "3005"}


def wall_course(cellcol, course, floor=Y0, tag="w"):
    """cellcol: dict (u,v)->colour for this course. merges runs, staggered by course parity."""
    bycol = defaultdict(set)
    for c, col in cellcol.items():
        bycol[col].add(c)
    for col, cs in bycol.items():
        def run(c, d):
            n = 1
            a = (c[0] - d[0], c[1] - d[1])
            while a in cs:
                n += 1; a = (a[0] - d[0], a[1] - d[1])
            b = (c[0] + d[0], c[1] + d[1])
            while b in cs:
                n += 1; b = (b[0] + d[0], b[1] + d[1])
            return n
        Hs, Vs = set(), set()
        for c in cs:
            (Hs if run(c, (1, 0)) >= run(c, (0, 1)) else Vs).add(c)
        groups = []
        for c in sorted(Hs, key=lambda t: (t[1], t[0])):
            if (c[0] - 1, c[1]) in Hs:
                continue
            L = 1
            while (c[0] + L, c[1]) in Hs: L += 1
            groups.append((c, L, 'h'))
        for c in sorted(Vs, key=lambda t: (t[0], t[1])):
            if (c[0], c[1] - 1) in Vs:
                continue
            L = 1
            while (c[0], c[1] + L) in Vs: L += 1
            groups.append((c, L, 'v'))
        for (c, L, d) in groups:
            seq = split_run(L)
            if course % 2: seq = seq[::-1]
            pos = 0
            for s in seq:
                if d == 'h':
                    x = (U(c[0] + pos) + U(c[0] + pos + s - 1)) / 2; z = V(c[1]); yaw = 0
                else:
                    x = U(c[0]); z = (V(c[1] + pos) + V(c[1] + pos + s - 1)) / 2; yaw = 90
                put(BR[s], col, x, ytop(course, floor), z, yaw, tag)
                pos += s


# ---------------------------------------------------------------- geometry of the plan
def rect(u0, u1, v0, v1): return {(u, v) for u in range(u0, u1 + 1) for v in range(v0, v1 + 1)}
def E(k): return rect(11 - k, 40 + k, 11 - k, 28 + k)


R = E(0)
ARCADE = E(1) - E(0)
CORR = E(3) - E(1)
INNER = E(4) - E(3)
ROOMS = E(10) - E(4)
OUTER = E(11) - E(10)
FOOT = E(11)

# partitions
PART = set()
for u in (12, 22, 32, 44):
    PART |= rect(u, u, 1, 6)
for v in (7, 16, 24, 32):
    PART |= rect(1, 6, v, v) | rect(45, 50, v, v)
for u in (12, 39):
    PART |= rect(u, u, 33, 38)
PART |= rect(23, 23, 33, 38) | rect(28, 28, 33, 38)
PART &= ROOMS | INNER   # partition cells live in room zone (or coincide with inner ring)
PART -= INNER

# doors:  (u0,v0,axis)  axis 'x' = opening spans 4 cells along u in a v-row wall
DOORS_N = [(8, 7, 'x'), (15, 7, 'x'), (25, 7, 'x'), (34, 7, 'x'), (44, 2, 'z')]
DOORS_W = [(7, 9, 'z'), (7, 18, 'z'), (7, 26, 'z')]
DOORS_E = [(44, 9, 'z'), (44, 18, 'z'), (44, 26, 'z')]
DOORS_S = [(8, 32, 'x'), (15, 32, 'x'), (31, 32, 'x'), (40, 32, 'x')]
DOORS = DOORS_N + DOORS_W + DOORS_E + DOORS_S
GATE = (24, 39, 'x')
PASSAGE = rect(24, 27, 32, 32)   # open passage through inner wall ring (lintel remains at course 5)


def door_cells(d):
    u, v, ax = d
    return {(u + i, v) for i in range(4)} if ax == 'x' else {(u, v + i) for i in range(4)}


# windows on outer walls: (u,v,axis) 2 cells at courses 2,3
WINDOWS = []
for u in (4, 16, 33, 45):
    WINDOWS.append((u, 39, 'x'))
for v in (11, 19, 27):
    WINDOWS.append((0, v, 'z'))
    WINDOWS.append((51, v, 'z'))
for u in (12, 20, 28, 36):
    WINDOWS.append((u, 32, 'x'))
for u in (12, 20, 30, 39):
    WINDOWS.append((u, 7, 'x'))
for v in (14, 23):
    WINDOWS.append((7, v, 'z'))
    WINDOWS.append((44, v, 'z'))
for u in (38, 48):
    WINDOWS.append((u, 39, 'x'))


def win_cells(w):
    u, v, ax = w
    return {(u + i, v) for i in range(2)} if ax == 'x' else {(u, v + i) for i in range(2)}


# ================================================================= BUILD
# ---- step 1: ground, baseplates, floors
step()
for sx in (-320, 320):
    for sz in (-320, 320):
        put("3811", GREEN, sx, 0, sz, 0, "base")

# floor plates (Y0=-8 => origin y=-8)
floor_cells = defaultdict(set)
for c in FOOT - R:
    if c in ROOMS and c[1] <= 6:
        floor_cells[PLINTH].add(c)
    elif c in CORR or c in ARCADE:
        floor_cells[TAN].add(c)
    else:
        floor_cells[DTAN].add(c)
# portal apron
APRON = rect(22, 29, 40, 40)
floor_cells[TAN] |= APRON
for col, cs in floor_cells.items():
    place_rects(pack(cs, PLATES), col, -8, "floor")

# courtyard checker paving (2x2 tiles) except fountain
for i in range(15):
    for j in range(9):
        if 6 <= i <= 8 and 3 <= j <= 5:
            continue
        if (i, j) in ((0, 0), (14, 0), (0, 8), (14, 8), (4, 4)):
            continue
        u = 11 + 2 * i; v = 11 + 2 * j
        col = PLATE_COL = (PLATINUM := 25) if (i + j) % 2 == 0 else TAN
        put("3068b", col, (U(u) + U(u + 1)) / 2, -8, (V(v) + V(v + 1)) / 2, 0, "court")

# front path / plaza (gx,gz coordinates)
path = set()
for gz in range(53, 64):
    for gx in range(32, 36):
        path.add((gx, gz))
for gz in range(53, 57):
    for gx in range(28, 40):
        path.add((gx, gz))
# the apron row (v=40) is at gz=52 -> already plates; path starts at gz 53 (v=41)
for gz in range(57, 64):
    for gx in (31, 36):
        path.add((gx, gz))
tw_g = lambda gx, gz: (cx(gx), cz(gz))
patcol = defaultdict(set)
for (gx, gz) in path:
    border = gx in (31, 36) or gx in (28, 39) or gz == 56 and False
    patcol[DTAN if border else TAN].add((gx, gz))
for col, cs in patcol.items():
    place_rects(pack(cs, TILES), col, -8, "path", tw_g)

# ---- step 2..: wall courses
# per-cell wall spec for the building
wall_h = {}
wall_kind = {}
for c in OUTER:
    wall_h[c] = 3 if c[1] == 0 else H
    wall_kind[c] = 'outer'
for c in INNER:
    wall_h[c] = H; wall_kind[c] = 'inner'
for c in PART:
    wall_h[c] = H; wall_kind[c] = 'part'

reserved = defaultdict(set)    # course -> cells filled by non-brick parts
void = set()
for d in DOORS + [GATE]:
    for c in door_cells(d):
        for k in range(H):
            reserved[k].add(c)
for c in PASSAGE:
    for k in range(5):
        reserved[k].add(c)
for w in WINDOWS:
    for c in win_cells(w):
        for k in (2, 3):
            reserved[k].add(c)


def wall_colour(c, k):
    kind = wall_kind[c]
    if kind == 'outer':
        if k == 0: return PLINTH
        if k == H - 1: return WHITE
        return WALL
    if kind == 'inner':
        if k == 0: return PLINTH
        if k == H - 1: return WHITE
        return WALL
    return WHITE


for k in range(H):
    step()
    cellcol = {c: wall_colour(c, k) for c in wall_h if k < wall_h[c] and c not in reserved[k]}
    wall_course(cellcol, k, tag="wall")

# ---- doors frames, windows
step()
for d in DOORS + [GATE]:
    u, v, ax = d
    cs = sorted(door_cells(d))
    xm = sum(U(a) for a, b in cs) / 4; zm = sum(V(b) for a, b in cs) / 4
    put("60596", WOOD, xm, Y0 - 144, zm, 0 if ax == 'x' else 90, "frame")
    if d == GATE:
        put("60623", PLINTH, xm - 36, Y0 - 144, zm, 0, "gate")
    elif d in DOORS_S + DOORS_W + DOORS_E:
        # closed leaf on the corridor side for roofed rooms
        if ax == 'x':
            put("60623", PLINTH, xm - 36, Y0 - 144, zm, 0, "leaf")
        else:
            put("60623", PLINTH, xm, Y0 - 144, zm + 36, 90, "leaf")
for w in WINDOWS:
    u, v, ax = w
    cs = sorted(win_cells(w))
    xm = sum(U(a) for a, b in cs) / 2; zm = sum(V(b) for a, b in cs) / 2
    yw = Y0 - 24 * 4
    yaw = 0 if ax == 'x' else 90
    put("60592", WHITE, xm, yw, zm, yaw, "win")
    put("60601", TRBLUE if False else 41, xm, yw, zm, yaw, "glass")

# ---- arcade: piers + arches
step()
ARCH6 = "3455"
corner_piers = [(10, 10), (41, 10), (10, 29), (41, 29)]
for (u, v) in corner_piers:
    for k in range(H):
        put("3005", WHITE, U(u), ytop(k), V(v), 0, "pier")
# N and S rows (v=10 and v=29): arches along u
for v in (10, 29):
    for b in range(5):
        u0 = 11 + 6 * b
        for u in (u0, u0 + 5):
            for k in range(5):
                put("3005", WHITE, U(u), ytop(k), V(v), 0, "pier")
        put(ARCH6, WHITE, (U(u0) + U(u0 + 5)) / 2, ytop(5), V(v), 0, "arch")
for u in (10, 41):
    for b in range(3):
        v0 = 11 + 6 * b
        for v in (v0, v0 + 5):
            for k in range(5):
                put("3005", WHITE, U(u), ytop(k), V(v), 0, "pier")
        put(ARCH6, WHITE, U(u), ytop(5), (V(v0) + V(v0 + 5)) / 2, 90, "arch")

# ---- portal pilasters + pediment (in front of gate, row v=40)
step()
for (ua, ub) in ((22, 23), (28, 29)):
    for k in range(7):
        put("3004", WHITE, (U(ua) + U(ub)) / 2, ytop(k), V(40), 0, "portal")
put("3008", WHITE, (U(22) + U(29)) / 2, ytop(7), V(40), 0, "portal")
put("3009", WHITE, (U(23) + U(28)) / 2, ytop(8), V(40), 0, "portal")
put("3010", WHITE, (U(24) + U(27)) / 2, ytop(9), V(40), 0, "portal")
put("3004", WHITE, (U(25) + U(26)) / 2, ytop(10), V(40), 0, "portal")
put("3070b", GOLD, U(25), ytop(11) + 16, V(40), 0, "portal") if False else None
px=(U(25)+U(26))/2
put("3005", GOLD, px, ytop(10) - 24 + 24 - 24 + 0 if False else ytop(11), V(40), 0, "portal")
put("3622", GOLD, px, ytop(12), V(40), 0, "portal")
put("3005", GOLD, px, ytop(13), V(40), 0, "portal")
# sun medallion on the lintel
put("4150", GOLD, (U(25) + U(26)) / 2, ytop(9) - 8 + 8 - 24 - 0, V(40) - 0, 0, "portal") if False else None

# ---- ceiling + roofs (S, W, E wings)
step()
WINGS = {
    'S': dict(cells=rect(0, 51, 29, 39), m=lambda l, d: (l, 39 - d), out=(0, 1), L0=0, L=52),
    'W': dict(cells=rect(0, 10, 11, 28), m=lambda l, d: (d, l), out=(-1, 0), L0=11, L=18),
    'E': dict(cells=rect(41, 51, 11, 28), m=lambda l, d: (51 - d, l), out=(1, 0), L0=11, L=18),
}
roof_cells = set()
for w in WINGS.values():
    roof_cells |= w['cells']
place_rects(pack(roof_cells, PLATES), ROOF, Y0 - 144 - 8, "ceil")


def yaw_for(dx, dz):
    return {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[(dx, dz)]


Ya = Y0 - 144 - 8 - 24      # course A origin
Yb = Ya - 24
for name, w in WINGS.items():
    m = w['m']; ox, oz = w['out']
    # course A mid bricks (d 3..7)
    mid = set()
    for l in range(w['L0'], w['L0'] + w['L']):
        for d in range(3, 8):
            mid.add(m(l, d))
    place_rects(pack(mid, BRICKS), ROOF, Ya, "roofA")
    for l in range(w['L0'], w['L0'] + w['L'], 2):
        def wpos(l_, d_):  # centre of cell pair
            a = m(l_, d_); b = m(l_ + 1, d_)
            return (U(a[0]) + U(b[0])) / 2, (V(a[1]) + V(b[1])) / 2
        # outer eave slope: d 0..2 descending outward, high at d=2
        x, z = wpos(l, 2); put("3298", ROOF, x, Ya, z, yaw_for(ox, oz), "eave")
        # inner eave: d 8..10 descending inward, high at d=8
        x, z = wpos(l, 8); put("3298", ROOF, x, Ya, z, yaw_for(-ox, -oz), "eave")
        # ridge slopes
        x, z = wpos(l, 4); put("3039", ROOF, x, Yb, z, yaw_for(ox, oz), "ridge")
        x, z = wpos(l, 6); put("3039", ROOF, x, Yb, z, yaw_for(-ox, -oz), "ridge")
    # ridge row d=5
    rr = {m(l, 5) for l in range(w['L0'], w['L0'] + w['L'])}
    place_rects(pack(rr, BRICKS), ROOF, Yb, "ridgebrick")
    rr2 = {m(l, 5) for l in range(w['L0'], w['L0'] + w['L'])}
    place_rects(pack(rr2, [(1, 8, "4162"), (1, 6, "6636"), (1, 4, "2431"), (1, 2, "3069b"), (1, 1, "3070b")]),
                PLINTH, Yb - 8, "ridgecap")

# ================================================================= TOWER
step()
TU0, TV0 = -6, 34          # tower cells u -6..-1, v 34..39
TW = 6
T_RING = {(u, v) for u in range(TU0, TU0 + TW) for v in range(TV0, TV0 + TW)}
T_IN = {(u, v) for u in range(TU0 + 1, TU0 + TW - 1) for v in range(TV0 + 1, TV0 + TW - 1)}
T_RING -= T_IN
TH = 12
# floor plate for tower base on baseplate? tower sits on floor plates at Y0 (same as building)
place_rects(pack(T_RING | T_IN, PLATES), WHITE, -8, "tfloor")
slits = set()
for k in (3, 4, 8, 9):
    slits.add((TU0 + 2, TV0 + TW - 1, k)); slits.add((TU0, TV0 + 2, k))
    slits.add((TU0 + 3, TV0, k)); slits.add((TU0 + TW - 1, TV0 + 3, k))
for k in range(TH):
    step()
    col = PLINTH if k in (0, 11) else WHITE
    cellcol = {c: col for c in T_RING if (c[0], c[1], k) not in slits}
    wall_course(cellcol, k, tag="tower")
# belfry
step()
bk0 = TH
place_rects(pack(T_RING | T_IN, PLATES), PLINTH, Y0 - 24 * TH - 8, "tplat")
Yf = Y0 - 24 * TH - 8           # belfry floor top
def yb(k): return Yf - 24 * (k + 1)
piers = [(TU0, TV0), (TU0 + 5, TV0), (TU0, TV0 + 5), (TU0 + 5, TV0 + 5),
         (TU0, TV0 + 1), (TU0, TV0 + 4), (TU0 + 5, TV0 + 1), (TU0 + 5, TV0 + 4)]
for (u, v) in piers:
    for k in range(4):
        put("3005", WHITE, U(u), yb(k), V(v), 0, "belfry")
for v in (TV0, TV0 + 5):
    put("3455", WHITE, (U(TU0) + U(TU0 + 5)) / 2, yb(4), V(v), 0, "belfryarch")
for u in (TU0, TU0 + 5):
    put("3659", WHITE, U(u), yb(4), (V(TV0 + 1) + V(TV0 + 4)) / 2, 90, "belfryarch")
# bell on floor, centred 2x2 block
bx = (U(TU0 + 2) + U(TU0 + 3)) / 2; bz = (V(TV0 + 2) + V(TV0 + 3)) / 2
put("3942c", GOLD, bx, Yf - 48, bz, 0, "bell")
# cornice plates above arches
step()
Yc = yb(4) - 8
ring6 = T_RING | T_IN
place_rects(pack(ring6, PLATES), PLINTH, Yc, "tcornice")
# pyramid roof
step()
Yr = Yc - 24
def cell_pair_center(ua, va, ub, vb): return (U(ua) + U(ub)) / 2, (V(va) + V(vb)) / 2
# corner double convex slopes 3045 (origin at the high corner cell? bounds x -10..30, z -30..10)
# 3045 high stud at origin cell; slopes toward -z and +x. place with yaw so slopes face outward.
corners = {  # corner cell block (u,v of high cell), yaw
    (TU0 + 1, TV0 + 1): 0,    # NW block: need slopes towards -x and -z
}
# use explicit placements: high cell is the inner cell of each 2x2 corner block
def put_corner(hu, hv, yaw):
    put("3045", ROOF, U(hu), Yr, V(hv), yaw, "pyr")
put_corner(TU0 + 1, TV0 + 1, 90)      # NW: descend -z and -x? verified visually
put_corner(TU0 + 4, TV0 + 1, 0)
put_corner(TU0 + 4, TV0 + 4, 270)
put_corner(TU0 + 1, TV0 + 4, 180)
# side slopes 3039 (2 deep) between corners: high cell inner
put("3039", ROOF, (U(TU0 + 2) + U(TU0 + 3)) / 2, Yr, V(TV0 + 1), 0, "pyr")           # north: descend -z
put("3039", ROOF, (U(TU0 + 2) + U(TU0 + 3)) / 2, Yr, V(TV0 + 4), 180, "pyr")         # south: descend +z
put("3039", ROOF, U(TU0 + 1), Yr, (V(TV0 + 2) + V(TV0 + 3)) / 2, 90, "pyr")          # west : descend -x
put("3039", ROOF, U(TU0 + 4), Yr, (V(TV0 + 2) + V(TV0 + 3)) / 2, 270, "pyr")         # east : descend +x
put("3003", ROOF, bx, Yr, bz, 0, "pyr")
# finial
put("3941", WHITE, bx, Yr - 24, bz, 0, "finial")
put("98100", GOLD, bx, Yr - 48, bz, 0, "finial")
put("3005", GOLD, bx, Yr - 72, bz, 0, "finial")
put("3622", GOLD, bx, Yr - 96, bz, 90, "finial")
put("3005", GOLD, bx, Yr - 120, bz, 0, "finial")

# ================================================================= COURTYARD
step()
# fountain  u 23..28, v 17..22
fu0, fu1, fv0, fv1 = 23, 28, 17, 22
fx = (U(fu0) + U(fu1)) / 2; fz = (V(fv0) + V(fv1)) / 2
put("3958", WHITE, fx, -8, fz, 0, "fount")
put("3009", WHITE, fx, -32, V(fv0), 0, "fount")
put("3009", WHITE, fx, -32, V(fv1), 0, "fount")
put("3010", WHITE, U(fu0), -32, (V(fv0 + 1) + V(fv1 - 1)) / 2, 90, "fount")
put("3010", WHITE, U(fu1), -32, (V(fv0 + 1) + V(fv1 - 1)) / 2, 90, "fount")
put("3031", TRBLUE, fx, -16, fz, 0, "water")
put("3941", WHITE, fx, -40, fz, 0, "fount")
put("3941", WHITE, fx, -64, fz, 0, "fount")
put("98100", TRBLUE, fx, -88, fz, 0, "fount")
put("6141", TRBLUE, fx, -96, fz, 0, "fount")
for (u, v) in ((fu0, fv0), (fu1, fv0), (fu0, fv1), (fu1, fv1)):
    put("3005", PLINTH, U(u), -56, V(v), 0, "fount")
# tiles ring of white 1x2 tiles on the rim
# planters in courtyard corners
def planter(u0, v0, wu, wv, flowers=(MAGENTA, PINK, 4)):
    cells = [(u0 + i, v0 + j) for i in range(wu) for j in range(wv)]
    cs = set(cells)
    place_rects(pack(cs, [(1, 4, "3010"), (1, 2, "3004"), (1, 1, "3005"), (2, 2, "3003")]), WOOD, -24, "planter")
    place_rects(pack(cs, PLATES[-7:]), GREEN, -32, "planter")
    for (u, v) in cells:
        put("3742", random.choice(flowers), U(u), -40, V(v), 0, "flower")
for (u0, v0) in ((11, 11), (39, 11), (11, 27), (39, 27)):
    planter(u0, v0, 2, 2)

# minifig with sombrero on a plate near the fountain
mfx, mfz = (U(19) + U(20)) / 2, (V(19) + V(20)) / 2
put("3022", DTAN, mfx, -8, mfz, 0, "mfplate")
ty = -8 - 72
mx = mfx
put("973", RED, mx, ty, mfz, 0, "mf")
put("3815b", BLUE, mx, ty + 32, mfz, 0, "mf")
put("3816c", BLUE, mx, ty + 44, mfz, 0, "mf")
put("3817c", BLUE, mx, ty + 44, mfz, 0, "mf")
put("3626c", 14, mx, ty - 27, mfz, 0, "mf")
put("90388", WOOD, mx, ty - 37, mfz, 0, "mf")
put("3819", RED, mx + 15.5, ty + 9, mfz, 0, "mf")
put("3818", RED, mx - 15.5, ty + 9, mfz, 0, "mf")
put("3820", 14, mx + 22, ty + 28, mfz, 0, "mf")
put("3820", 14, mx - 22, ty + 28, mfz, 0, "mf")

# ================================================================= OPEN WING FURNITURE (north wing, v 1..6)
step()
FL = -8  # floor top (wood plates, same level)
def Yc_(k, h=1): return FL - 24 * (k + h)

def brick(ref, col, u, v, k=0, yaw=0, du=0, dv=0):
    put(ref, col, U(u) + du, Yc_(k), V(v) + dv, yaw, "furn")

def rectbrick(ref, col, u0, u1, v0, v1, k=0, yaw=0):
    put(ref, col, (U(u0) + U(u1)) / 2, Yc_(k), (V(v0) + V(v1)) / 2, yaw, "furn")

def plate(ref, col, u0, u1, v0, v1, ytop_, yaw=0):
    put(ref, col, (U(u0) + U(u1)) / 2, ytop_, (V(v0) + V(v1)) / 2, yaw, "furn")

# R1 bedroom [1..11]
rectbrick("3001", WOOD, 2, 3, 1, 4, 0, 90 if False else 90)     # bed base 2 wide (u2-3) x 4 long (v1-4)
plate("3021", RED, 2, 3, 2, 4, FL - 24 - 8, 90)
plate("3023b", WHITE, 2, 3, 1, 1, FL - 24 - 8, 0)
rectbrick("3004", WOOD, 2, 3, 0 + 1, 1 + 0, 1, 0) if False else None
brick("3005", WOOD, 5, 1)                     # nightstand
put("3062b", TRYEL, U(5), Yc_(1), V(1), 0, "furn")
rectbrick("3622", WOOD, 9, 11, 1, 1, 0); rectbrick("3622", WOOD, 9, 11, 1, 1, 1); rectbrick("3622", WOOD, 9, 11, 1, 1, 2)
plate("87079", PLINTH, 5, 8, 3, 4, FL - 8, 0)          # rug
plate("3068b", RED, 8, 9, 5, 6, FL - 8, 0) if False else None

# R2 dining [13..21]
for (u, v) in ((15, 2), (18, 2), (15, 3), (18, 3)):
    put("3062b", WOOD, U(u), Yc_(0), V(v), 0, "furn")
plate("3020", WOOD, 15, 18, 2, 3, FL - 24 - 8, 0)
for (u, v) in ((16, 1), (17, 1)):
    brick("3005", PLINTH, u, v)
for (u, v) in ((16, 4), (17, 4)):
    brick("3005", PLINTH, u, v)
    brick("3005", PLINTH, u, v + 1)
    brick("3005", PLINTH, u, v + 1, 1)
put("3062b", YELLOW, U(16), Yc_(1), V(2) , 0, "furn") if False else None
put("3062b", TRYEL, U(16), FL - 24 - 8 - 24, V(2), 0, "furn")
# sideboard at rear + vase
rectbrick("3010", WOOD, 19, 21, 1, 1, 0) if False else None
rectbrick("3622", WOOD, 19, 21, 1, 1, 0)
rectbrick("3622", WOOD, 19, 21, 1, 1, 1)
put("7077", PLINTH, U(14), FL - 16, V(5) + 0, 0, "furn") if False else None

# R3 kitchen [23..31]
rectbrick("3008", WHITE, 24, 31, 1, 1, 0)
plate("3460", TAN, 24, 31, 1, 1, FL - 24 - 8, 0)
rectbrick("3003", BLACK, 26, 27, 2, 3, 0)                       # stove
put("3068b", DBG, U(26) + 10, FL - 24 - 8, V(2) + 10 + 10 - 10 + 0, 0, "furn") if False else None
put("3068b", DBG, (U(26) + U(27)) / 2, FL - 48 + 0, (V(2) + V(3)) / 2, 0, "furn") if False else None
put("3068b", DBG, (U(26) + U(27)) / 2, FL - 24 - 8, (V(2) + V(3)) / 2, 0, "furn")
put("4528", 0, U(26) + 10, FL - 24 - 8 - 12, V(2) + 10, 0, "furn") if False else None
put("2489", WOOD, (U(30) + U(31)) / 2, FL - 40, (V(5) + V(6)) / 2, 0, "furn")
put("2489", WOOD, (U(28) + U(29)) / 2, FL - 40, (V(5) + V(6)) / 2, 0, "furn")
put("3003", WOOD, (U(24) + U(25)) / 2, Yc_(0), (V(4) + V(5)) / 2, 0, "furn")     # small prep table
put("3022", TAN, (U(24) + U(25)) / 2, FL - 24 - 8, (V(4) + V(5)) / 2, 0, "furn")
put("3899", RED, U(24), FL - 24 - 8 - 24, V(4), 0, "furn") if False else None
for (u, col) in ((24, PLINTH), (26, YELLOW), (30, GREEN)):
    put("6141", col, U(u), FL - 24 - 8 - 8, V(1), 0, "furn")

# R4 sala [33..43]
rectbrick("3001", PLINTH if False else RED, 34, 37, 1, 2, 0, 0)     # sofa seat 4x2
rectbrick("3010", RED, 34, 37, 1, 1, 1, 0)                             # sofa back
brick("3005", RED, 33, 1); brick("3005", RED, 38, 1)
brick("3005", RED, 33, 1, 1); brick("3005", RED, 38, 1, 1)
plate("3020", PLINTH, 34, 37, 4, 5, FL - 8, 0)                           # rug
put("3003", WOOD, (U(35) + U(36)) / 2, Yc_(0) - 8, (V(4) + V(5)) / 2, 0, "furn")
put("3068b", WOOD, (U(35) + U(36)) / 2, FL - 24 - 16, (V(4) + V(5)) / 2, 0, "furn")
put("3003", PLINTH, (U(41) + U(42)) / 2, Yc_(0), (V(1) + V(2)) / 2, 0, "furn") if False else None
put("3003", PLINTH, (U(41) + U(42)) / 2 - 0, Yc_(0), (V(1) + V(2)) / 2, 0, "furn") if False else None
put("3003", PLINTH, (U(41) + U(42)) / 2 - 20 if False else (U(41) + U(42)) / 2, Yc_(0), (V(5) + V(6)) / 2, 0, "furn")
put("4727", GREEN, (U(41) + U(42)) / 2, FL - 24 - 8 + 8 - 8 + 0 - 0, (V(5) + V(6)) / 2, 0, "furn") if False else None
put("4727", GREEN, (U(41) + U(42)) / 2, FL - 24 - 0 - 0, (V(5) + V(6)) / 2, 0, "furn")

# R5 study [45..50]
rectbrick("3009", WOOD, 45, 50, 1, 1, 0)
for i, u in enumerate((45, 47, 48, 50)):
    brick("3005", (RED, BLUE, 14, GREEN)[i], u, 1, 1)
rectbrick("3666", WOOD, 45, 50, 1, 1, 2) if False else None
for (u, v) in ((46, 3), (49, 3), (46, 4), (49, 4)):
    put("3062b", WOOD, U(u), Yc_(0), V(v), 0, "furn")
plate("3020", WOOD, 46, 49, 3, 4, FL - 24 - 8, 0)
put("3062b", TRYEL, U(46), FL - 24 - 8 - 24, V(3), 0, "furn")
brick("3005", PLINTH, 47, 5)
brick("3005", PLINTH, 47, 6)
brick("3005", PLINTH, 47, 6, 1)

# ================================================================= GARDEN, PLANTS, DETAIL
step()
GY = 0  # baseplate surface
def gfurn(ref, col, gx, gz, yy, yaw=0, tag="garden"):
    put(ref, col, cx(gx), yy, cz(gz), yaw, tag)

# trees (trunk + two leaf layers)
def tree(gx, gz, h=4):
    for k in range(h):
        gfurn("3062b", WOOD, gx, gz, -24 * (k + 1))
    top = -24 * h
    gfurn("2417", DGREEN, gx, gz, top - 8, 0, "leaf")
    gfurn("2423", GREEN, gx, gz, top - 16, 90, "leaf")
tree(14, 6); tree(30, 4); tree(46, 6); tree(58, 5); tree(4, 22); tree(3, 40)

# cacti
def cactus(gx, gz, h=3):
    for k in range(h):
        gfurn("3062b", GREEN, gx, gz, -24 * (k + 1), 0, "cactus")
    gfurn("3742", PINK, gx, gz, -24 * h - 8, 0, "cactus")
for (gx, gz) in ((10, 2), (22, 8), (38, 6), (53, 2), (62, 20), (62, 34), (1, 30)):
    cactus(gx, gz, random.choice((2, 3)))
# agaves (leaf plates on round plates)
for (gx, gz) in ((18, 3), (40, 3), (61, 12), (6, 18), (5, 44), (61, 44), (26, 58), (41, 58)):
    gfurn("6141", GREEN, gx, gz, -8, 0, "agave")
    gfurn("32607", DGREEN, gx, gz, -16, random.choice((0, 90, 180, 270)), "agave")

# front planters flanking the gate along the wall (v=41? v=40 row), at ground level
for (ua, ub) in ((13, 20), (31, 38)):
    cells = {(u, 40) for u in range(ua, ub + 1)}
    place_rects(pack(cells, [(1, 8, "3008"), (1, 4, "3010"), (1, 2, "3004"), (1, 1, "3005")]), WOOD, -24, "fplanter")
    place_rects(pack(cells, [(1, 8, "3460"), (1, 4, "3710"), (1, 2, "3023b"), (1, 1, "3024")]), GREEN, -32, "fplanter")
    for u in range(ua, ub + 1):
        put("3742", random.choice((MAGENTA, PINK, 4, 14)), U(u), -40, V(40), 0, "fflower")
# barrels by the gate and in the front
for (gx, gz) in ((44, 55), (46, 55), (21, 55)):
    put("2489", WOOD, cx(gx), -40, cz(gz), 0, "barrel")
# lamps: posts flanking the path
for (gx, gz) in ((30, 58), (37, 58)):
    for k in range(3):
        gfurn("3062b", BLACK, gx, gz, -24 * (k + 1), 0, "lamp")
    gfurn("3062b", TRYEL, gx, gz, -24 * 4, 0, "lamp")
    gfurn("4589", BLACK, gx, gz, -24 * 5, 0, "lamp")
# rear garden path + hedge details: tan tiles in rear
rear = {(gx, gz) for gx in range(24, 44) for gz in (7, 8)}
place_rects(pack(rear, TILES), DTAN, -8, "rearpath", tw_g)
# bougainvillea on the west wall: magenta/pink flowers on wall-adjacent ground vines
for gz in range(24, 40, 3):
    gfurn("3062b", DGREEN, 7, gz, -24, 0, "vine")
    gfurn("3742", random.choice((MAGENTA, PINK)), 7, gz, -32, 0, "vine")
# buttresses (contrafuertes) on east and west outer walls, standing on the baseplate
for vv in (13, 21, 29):
    for (uh, ul, yw) in ((52, 53, 270), (-1, -2, 90)):
        xc = (U(uh) + U(ul)) / 2
        for k in range(4):
            put("3004", WHITE, xc, -24 * (k + 1), V(vv), 0, "buttress")
        put("3040b", WHITE, U(uh), -24 * 5, V(vv), yw, "buttress")

# ================================================================= WRITE
plan = {"version": 1, "author": "Carlos Antelo (generated with Claude)",
        "sections": [{"name": "hacienda.ldr",
                      "description": "Hacienda del Sol - Mexican courtyard hacienda with bell tower",
                      "steps": [s for s in steps if s]}]}
json.dump(plan, open(OUT, "w"), indent=0)
print("placements", sum(len(s) for s in steps), "steps", len([s for s in steps if s]))
