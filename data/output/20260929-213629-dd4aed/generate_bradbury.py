#!/usr/bin/env python3
"""Bradbury Building (Broadway & 3rd, Los Angeles) - original LDraw assembly generator.

Writes three editable JSON assembly plans (details / building / scene) for
`ldraw-agent build`.  No OMR geometry is copied; every placement is computed here.

Conventions (see output/NOTES.md)
  * negative Y is up; a part placed at y occupies y .. y+body_height (downwards),
    so resting on a surface whose top plane is T means y = T - body_height
  * sidewalk top surface is scene y = -8
  * bay pitch 80 LDU = 2-stud pier + 2-stud window
  * Broadway elevation faces -Z, 3rd Street elevation faces +X
  * the chamfered corner is 30505 "Brick 3 x 3 without Corner" (native cut at +X/-Z)

Every horizontal layer is generated from a *disjoint set of stud cells* and then
packed into real bricks/plates/tiles, which keeps the inventory realistic and makes
body overlaps structurally impossible within a layer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AUTHOR = "carlos.antelo@gmail.com via LDraw Astra agent"

# ---------------------------------------------------------------- palette ---
TAN, DTAN, RB, WHITE = 19, 28, 70, 15
LBG, DBG, BLACK = 71, 72, 0
TRANS, GOLD, DRED = 47, 297, 320
RED, GREEN, YELLOW = 4, 2, 14

# ---------------------------------------------- rectangle inventories ------
# (studs_x, studs_z, reference) in the part's native orientation
BRICK_RECTS = [
    (10, 2, "3006"), (8, 2, "3007"), (4, 2, "3001"), (3, 2, "3002"), (2, 2, "3003"),
    (8, 1, "3008"), (6, 1, "3009"), (4, 1, "3010"), (3, 1, "3622"), (2, 1, "3004"),
    (1, 1, "3005"),
]
PLATE_RECTS = [
    (16, 16, "91405"), (16, 8, "92438"), (8, 6, "3036"), (6, 6, "3958"),
    (8, 4, "3035"), (6, 4, "3032"), (4, 4, "3031"), (8, 2, "3034"),
    (6, 2, "3795"), (4, 2, "3020"), (3, 2, "3021"), (2, 2, "3022"),
    (8, 1, "3460"), (6, 1, "3666"), (4, 1, "3710"), (3, 1, "3623"),
    (2, 1, "3023b"), (1, 1, "3024"),
]
TILE_RECTS = [
    (4, 2, "87079"), (2, 2, "3068b"), (6, 1, "6636"), (4, 1, "2431"),
    (3, 1, "63864"), (2, 1, "3069b"), (1, 1, "3070b"),
]
GRILLE_RECTS = [(2, 1, "2877"), (1, 1, "3005")]
GRILLE_TILE_RECTS = [(2, 1, "2412b"), (1, 1, "3070b")]
LANDING_RECTS = [(3, 2, "3021"), (3, 1, "3623"), (2, 1, "3023b"), (1, 1, "3024")]

# ------------------------------------------------------------- geometry ----
X0, X1 = -480, 200            # building west / east outer faces
Z0, Z1 = -120, 480            # Broadway (south) / party (north) outer faces
NX, NZ = (X1 - X0) // 20, (Z1 - Z0) // 20        # 34 x 30 stud cells
FRONT_BAYS, RIGHT_BAYS = 7, 6

CORNER_C = (170, -90)         # chamfer block centre, cells ix31..33 / iz0..2
ENTRANCE_CELLS = range(15, 21)    # grand Broadway arch, 6 studs
ENTRANCE_X = -120

GROUND_COURSES, TYPICAL_COURSES = 5, 4
Y_GROUND = -8
PITCH_GROUND = 8 + 24 * GROUND_COURSES + 8       # 136
PITCH_TYPICAL = 8 + 24 * TYPICAL_COURSES + 8     # 112
Y_S1 = Y_GROUND - PITCH_GROUND                   # -144
Y_S2 = Y_S1 - PITCH_TYPICAL                      # -256
Y_S3 = Y_S2 - PITCH_TYPICAL                      # -368
Y_ARCADE = Y_S3 - PITCH_TYPICAL                  # -480
Y_TOP = Y_ARCADE - PITCH_TYPICAL                 # -592

# ---- cell sets -------------------------------------------------------------
FRONT_OUT = {(ix, 0) for ix in range(0, 31)}
FRONT_IN = {(ix, 1) for ix in range(0, 31)}
RIGHT_OUT = {(33, iz) for iz in range(3, 30)}
RIGHT_IN = {(32, iz) for iz in range(3, 30)}
CORNER_CELLS = {(ix, iz) for ix in (31, 32, 33) for iz in (0, 1, 2)}
LEFT_OUT = {(0, iz) for iz in range(2, 30)}
LEFT_IN = {(1, iz) for iz in range(2, 30)}
REAR_OUT = {(ix, 29) for ix in range(2, 32)}
REAR_IN = {(ix, 28) for ix in range(2, 32)}
PERIMETER = (FRONT_OUT | FRONT_IN | RIGHT_OUT | RIGHT_IN | CORNER_CELLS
             | LEFT_OUT | LEFT_IN | REAR_OUT | REAR_IN)
INTERIOR = {(ix, iz) for ix in range(2, 32) for iz in range(2, 28)} - CORNER_CELLS
FOOTPRINT = {(ix, iz) for ix in range(NX) for iz in range(NZ)}
COURT = {(ix, iz) for ix in range(5, 29) for iz in range(5, 25)}   # 24 x 20 studs
GALLERY = INTERIOR - COURT

# window / arch cells
FRONT_WINDOWS = {3 + 4 * i for i in range(FRONT_BAYS)} | {4 + 4 * i for i in range(FRONT_BAYS)}
RIGHT_WINDOWS = {5 + 4 * j for j in range(RIGHT_BAYS)} | {6 + 4 * j for j in range(RIGHT_BAYS)}
FRONT_ARCH_SPAN = set(range(2, 30))     # union of the seven 4-stud arch footprints
RIGHT_ARCH_SPAN = set(range(4, 28))
# wider ground-floor shop openings: 3-stud bay with a single-stud stone pier
GROUND_FRONT_WINDOWS = {3 + 4 * i for i in range(FRONT_BAYS)} | \
    {4 + 4 * i for i in range(FRONT_BAYS)} | {5 + 4 * i for i in range(FRONT_BAYS)}
GROUND_RIGHT_WINDOWS = {5 + 4 * j for j in range(RIGHT_BAYS)} | \
    {6 + 4 * j for j in range(RIGHT_BAYS)} | {7 + 4 * j for j in range(RIGHT_BAYS)}
PARTY_WINDOWS = {4, 5, 8, 9, 12, 13, 16, 17, 20, 21, 24, 25}
REAR_WINDOWS = PARTY_WINDOWS | {28, 29}
END_PIER_FRONT = {0, 1, 2}
END_PIER_RIGHT = {27, 28, 29}

LIFT_A_CELLS = {(ix, iz) for ix in range(24, 28) for iz in range(6, 12)}
LIFT_B_CELLS = {(ix, iz) for ix in range(24, 28) for iz in range(16, 22)}
STAIR_CELLS = {(ix, iz) for ix in range(17, 21) for iz in range(13, 25)}
FITTING_CELLS = LIFT_A_CELLS | LIFT_B_CELLS | STAIR_CELLS
CT_X0, CT_X1 = X0 + 20 * 5, X0 + 20 * 29     # -380 .. 100
CT_Z0, CT_Z1 = Z0 + 20 * 5, Z0 + 20 * 25     # -20 .. 380


def wx(ix):
    return X0 + 20 * ix


def wz(iz):
    return Z0 + 20 * iz


# -------------------------------------------------------------- helpers ----
def ref_of(ref):
    return ref if (ref.startswith("@") or "." in ref) else ref + ".dat"


def P(pid, ref, colour, at, **kw):
    d = {"id": pid, "ref": ref_of(ref), "colour": colour,
         "at": [round(float(v), 3) for v in at]}
    d.update(kw)
    return d


def pack(cells, rects, reverse=False, rotate=True):
    """Greedy largest-first rectangle cover of a stud-cell set.

    `reverse` anchors rectangles at the far corner instead of the near one, which
    gives a different tiling; stacking a forward and a reverse layer bridges the
    seams of both, so a plate ring is genuinely bonded rather than merely abutting.
    """
    remaining = set(cells)
    options = []
    for dx, dz, ref in rects:
        options.append((dx, dz, ref, 0))
        if rotate and dx != dz:
            options.append((dz, dx, ref, 90))
    options.sort(key=lambda o: (-o[0] * o[1], -max(o[0], o[1])))
    out = []
    while remaining:
        if reverse:
            jx, jz = max(remaining, key=lambda c: (c[1], c[0]))
        else:
            jx, jz = min(remaining, key=lambda c: (c[1], c[0]))
        for w, h, ref, yaw in options:
            ix, iz = (jx - w + 1, jz - h + 1) if reverse else (jx, jz)
            block = [(ix + a, iz + b) for a in range(w) for b in range(h)]
            if all(c in remaining for c in block):
                remaining.difference_update(block)
                out.append((ix, iz, w, h, ref, yaw))
                break
        else:
            remaining.discard((jx, jz))
    return out


def emit(out, tag, cells, colour, y, rects, purpose=None, ox=None, oz=None,
         reverse=False, rotate=True):
    ox = X0 if ox is None else ox
    oz = Z0 if oz is None else oz
    for n, (ix, iz, w, h, ref, yaw) in enumerate(pack(cells, rects, reverse, rotate)):
        kw = {"yaw": 90} if yaw else {}
        if purpose and n == 0:
            kw["purpose"] = purpose
        out.append(P(f"{tag}-{n}", ref, colour,
                     [ox + 20 * ix + 10 * w, y, oz + 20 * iz + 10 * h], **kw))


def column(out, tag, x, z, y_bottom, height, colour, brick="3062b", plate="3024"):
    """Stack 24-LDU bricks then 8-LDU plates upward from bottom plane y_bottom."""
    n_brick, rest = divmod(height, 24)
    n_plate, extra = divmod(rest, 8)
    assert extra == 0, (tag, height)
    y = y_bottom
    k = 0
    for _ in range(n_brick):
        y -= 24
        out.append(P(f"{tag}-b{k}", brick, colour, [x, y, z]))
        k += 1
    for _ in range(n_plate):
        y -= 8
        out.append(P(f"{tag}-p{k}", plate, colour, [x, y, z]))
        k += 1


def section(name, description, steps, anchors=None):
    d = {"name": name + ".ldr", "description": description,
         "steps": [s for s in steps if s]}
    if anchors:
        d["anchors"] = anchors
    return d


def write(path, sections, **kw):
    payload = {"version": 1, "author": AUTHOR, "sections": sections}
    payload.update(kw)
    path.write_text(json.dumps(payload, indent=1) + "\n")


# ------------------------------------------------------------- storeys -----
def storey(name, kind):
    ground = kind == "ground"
    arcade = kind == "arcade"
    courses = GROUND_COURSES if ground else TYPICAL_COURSES
    top = -24 * courses
    steps = []

    # ---- 1. floor deck -----------------------------------------------------
    deck = []
    deck_cells = FOOTPRINT if ground else FOOTPRINT - COURT
    if arcade:
        # corbelled belt course: a 2-stud band along both street elevations,
        # one stud proud of the wall face.  Disjoint from the deck by construction.
        ring = ({(ix, iz) for ix in range(0, 34) for iz in (-1, 0)}
                | {(ix, iz) for ix in (33, 34) for iz in range(-1, 30)})
        emit(deck, "corbel", ring, RB, 0, PLATE_RECTS,
             purpose="Corbelled belt course announcing the top-floor arcade")
        deck_cells = deck_cells - {c for c in ring if 0 <= c[0] < NX and 0 <= c[1] < NZ}
    emit(deck, "deck", deck_cells, TAN, 0, PLATE_RECTS,
         purpose="Floor slab; above ground it is a ring so the light court stays open")
    if not ground:
        emit(deck, "gal", GALLERY, TAN, -8, PLATE_RECTS, reverse=True,
             purpose="Second staggered plate layer stiffening the gallery cantilever")
    steps.append(deck)

    # ---- 2. wall courses ---------------------------------------------------
    for c in range(courses):
        y = -24 * (c + 1)
        first, last = c == 0, c == courses - 1
        window_course = 1 <= c <= (3 if ground else 2)
        row = []

        if ground:
            body = LBG if first else (RB if last else WHITE)
        else:
            body = RB if first else TAN
        inner_col = BLACK if window_course else TAN
        if ground and c == 3:
            inner_col = WHITE          # illuminated shopfront sign band

        blocked = {(ix, 0) for ix in ENTRANCE_CELLS} | {(ix, 1) for ix in ENTRANCE_CELLS} \
            if ground else set()

        # ---- outer skin ----------------------------------------------------
        out_cells = (FRONT_OUT | RIGHT_OUT) - blocked
        specials = []
        if arcade and c == 1:
            for i in range(FRONT_BAYS):
                specials.append(P(f"farch-{i}", "6182", RB, [-400 + 80 * i, -72, Z0 + 10],
                                  **({"purpose": "Round-arch arcade; neighbouring arches share each pier"}
                                     if i == 0 else {})))
            for j in range(RIGHT_BAYS):
                specials.append(P(f"rarch-{j}", "6182", RB, [X1 - 10, -72, 80 * j], yaw=90))
            out_cells -= {(ix, 0) for ix in FRONT_ARCH_SPAN}
            out_cells -= {(33, iz) for iz in RIGHT_ARCH_SPAN}
        elif arcade and c == 2:
            out_cells -= {(ix, 0) for ix in FRONT_ARCH_SPAN}
            out_cells -= {(33, iz) for iz in RIGHT_ARCH_SPAN}
        elif last and not ground:
            for i in range(FRONT_BAYS):
                specials.append(P(f"fhead-{i}", "3659", DTAN, [-400 + 80 * i, y, Z0 + 10],
                                  **({"purpose": "Arch 1 x 4 window head, one per bay"} if i == 0 else {})))
            for j in range(RIGHT_BAYS):
                specials.append(P(f"rhead-{j}", "3659", DTAN, [X1 - 10, y, 80 * j], yaw=90))
            out_cells -= {(ix, 0) for ix in FRONT_ARCH_SPAN}
            out_cells -= {(33, iz) for iz in RIGHT_ARCH_SPAN}
        elif window_course:
            fw = GROUND_FRONT_WINDOWS if ground else FRONT_WINDOWS
            rw = GROUND_RIGHT_WINDOWS if ground else RIGHT_WINDOWS
            out_cells -= {(ix, 0) for ix in fw}
            out_cells -= {(33, iz) for iz in rw}
        # reddish-brown corner pilasters frame each elevation
        pil = ({(ix, 0) for ix in END_PIER_FRONT} | {(33, iz) for iz in END_PIER_RIGHT}) & out_cells
        emit(row, f"o{c}", out_cells - pil, body, y, BRICK_RECTS)
        emit(row, f"op{c}", pil, RB if not ground else LBG, y, BRICK_RECTS)
        row += specials

        # ---- inner backing skin --------------------------------------------
        emit(row, f"i{c}", (FRONT_IN | RIGHT_IN) - blocked, inner_col, y, BRICK_RECTS,
             purpose="Dark inner backing gives every window a true one-stud reveal"
             if (window_course and c == 1) else None)

        # ---- chamfered corner ----------------------------------------------
        corner_col = BLACK if window_course else (LBG if (ground and first) else (WHITE if ground else RB))
        row.append(P(f"corner{c}", "30505", corner_col, [CORNER_C[0], y, CORNER_C[1]],
                     **({"purpose": "45 degree chamfer; black courses read as the corner window"}
                        if c == 1 else {})))

        # ---- quiet party walls: plain punched openings, no arches or sills ---
        party_out = LEFT_OUT | REAR_OUT
        party_in_col = TAN
        if window_course:
            party_out = party_out - {(0, iz) for iz in PARTY_WINDOWS} \
                                  - {(ix, 29) for ix in REAR_WINDOWS}
            party_in_col = BLACK
        emit(row, f"po{c}", party_out, RB, y, BRICK_RECTS,
             purpose="Secondary elevations keep a plainer punched-window rhythm"
             if c == 1 else None)
        emit(row, f"pi{c}", LEFT_IN | REAR_IN, party_in_col, y, BRICK_RECTS)
        steps.append(row)

    # ---- 2b. projecting sills give every window a real shadow line ---------
    if not arcade:
        sills = []
        sill_col = WHITE if ground else RB
        fw = sorted(GROUND_FRONT_WINDOWS if ground else FRONT_WINDOWS)
        rw = sorted(GROUND_RIGHT_WINDOWS if ground else RIGHT_WINDOWS)
        blocked_ix = set(ENTRANCE_CELLS) if ground else set()
        runs = []
        for grp in (fw,):
            i = 0
            while i < len(grp):
                j = i
                while j + 1 < len(grp) and grp[j + 1] == grp[j] + 1:
                    j += 1
                runs.append((grp[i], grp[j] - grp[i] + 1))
                i = j + 1
        for n, (start, width) in enumerate(runs):
            if start in blocked_ix or (start + width - 1) in blocked_ix:
                continue
            for k in range(width // 2):
                sills.append(P(f"sillf-{n}-{k}", "3022", sill_col,
                               [wx(start) + 40 * k + 20, -32, Z0],
                               **({"purpose": "Projecting sill: one stud proud, one stud bearing"}
                                  if n == 0 and k == 0 else {})))
            if width % 2:
                sills.append(P(f"sillfo-{n}", "3023b", sill_col,
                               [wx(start + width - 1) + 10, -32, Z0], yaw=90))
        rruns = []
        i = 0
        while i < len(rw):
            j = i
            while j + 1 < len(rw) and rw[j + 1] == rw[j] + 1:
                j += 1
            rruns.append((rw[i], rw[j] - rw[i] + 1))
            i = j + 1
        for n, (start, width) in enumerate(rruns):
            for k in range(width // 2):
                sills.append(P(f"sillr-{n}-{k}", "3022", sill_col,
                               [X1, -32, wz(start) + 40 * k + 20]))
            if width % 2:
                sills.append(P(f"sillro-{n}", "3023b", sill_col,
                               [X1, -32, wz(start + width - 1) + 10]))
        sills.append(P("sill-corner", "2450", sill_col, [CORNER_C[0] + 20, -32, CORNER_C[1] - 20],
                       purpose="Pale chamfer sill making the corner bay read as the focal feature"))
        steps.append(sills)

    # ---- 3. band plate: cross-bonds both wall skins and reads as a string course
    band = []
    band_cells = PERIMETER - CORNER_CELLS
    emit(band, "band", band_cells, RB, top - 8, PLATE_RECTS,
         purpose="Two-stud band plate cross-bonds the outer and inner wall skins")
    band.append(P("band-corner", "2450", RB, [CORNER_C[0], top - 8, CORNER_C[1]]))
    steps.append(band)

    # ---- 4. storey-specific features ---------------------------------------
    if ground:
        feat = [P("grand-arch", "30613", RB, [ENTRANCE_X, -120, Z0 + 30],
                  purpose="Ornamented 6-stud entrance arch, exactly one storey tall")]
        feat.append(P("step-a", "3020", LBG, [ENTRANCE_X - 40, -8, Z0 - 20]))
        feat.append(P("step-b", "3020", LBG, [ENTRANCE_X + 40, -8, Z0 - 20]))
        steps.append(feat)

        # the famous patterned court floor
        tiles = []
        ring1 = {c for c in COURT if c[0] in (5, 28) or c[1] in (5, 24)}
        ring2 = {c for c in COURT if c[0] in (7, 26) or c[1] in (7, 22)} - ring1
        motif = {c for c in COURT if 12 <= c[0] <= 21 and 11 <= c[1] <= 18}
        field = COURT - ring1 - ring2 - motif - FITTING_CELLS
        emit(tiles, "ct-field", field, TAN, -8, TILE_RECTS,
             purpose="Patterned light-court floor")
        emit(tiles, "ct-r1", ring1 - FITTING_CELLS, RB, -8, TILE_RECTS)
        emit(tiles, "ct-r2", ring2 - FITTING_CELLS, DTAN, -8, TILE_RECTS)
        emit(tiles, "ct-motif", motif - FITTING_CELLS, DTAN, -8, TILE_RECTS)
        emit(tiles, "ct-fit", FITTING_CELLS, DTAN, -8, PLATE_RECTS,
             purpose="Studded plates, not tiles, where the stair and elevators land")
        steps.append(tiles)
    else:
        rail = []
        for k in range(6):
            cx = CT_X0 + 80 * k + 40
            rail.append(P(f"rail-s{k}", "19121", GOLD, [cx, -56, CT_Z0 - 10],
                          **({"purpose": "Ornamental iron balustrade around the light court"}
                             if k == 0 else {})))
            if k != 3:      # opening where the oak stair lands
                rail.append(P(f"rail-n{k}", "19121", GOLD, [cx, -56, CT_Z1 + 10], yaw=180))
        for k in range(5):
            cz = CT_Z0 + 80 * k + 40
            rail.append(P(f"rail-w{k}", "19121", GOLD, [CT_X0 - 10, -56, cz], yaw=90))
            rail.append(P(f"rail-e{k}", "19121", GOLD, [CT_X1 + 10, -56, cz], yaw=-90))
        for n, (cx, cz) in enumerate(((CT_X0 - 10, CT_Z0 - 10), (CT_X1 + 10, CT_Z0 - 10),
                                      (CT_X0 - 10, CT_Z1 + 10), (CT_X1 + 10, CT_Z1 + 10))):
            rail.append(P(f"post-{n}", "3062b", GOLD, [cx, -32, cz]))
            rail.append(P(f"postb-{n}", "3062b", GOLD, [cx, -56, cz]))
        steps.append(rail)

    anchors = {"base": {"at": [0, 8, 0]}, "next": {"at": [0, top - 8, 0]}}
    desc = {
        "ground": "Stone-faced ground storey: shopfront bays, the ornamented Broadway entrance arch, "
                  "the recessed chamfer doorway and the patterned light-court floor",
        "typical": "Typical office storey: tan brick piers, one-stud recessed windows with arch heads, "
                   "and a cantilevered gallery with an ornamental iron balustrade",
        "arcade": "Top-floor round-arch arcade over a corbelled belt course, with its gallery",
    }[kind]
    return section(name, desc, steps, anchors)


# ------------------------------------------------------------- cornice -----
# Each ring is emitted as four disjoint strips (right, front, left, rear) so the
# packer works along a strip and never leaves an unbonded single-stud column.
RING_A = [
    {(ix, iz) for ix in (32, 33, 34) for iz in range(-1, 30)},
    {(ix, iz) for ix in range(0, 32) for iz in (-1, 0, 1)},
    {(ix, iz) for ix in (0, 1) for iz in range(2, 30)},
    {(ix, iz) for ix in range(2, 32) for iz in (28, 29)},
]
RING_B = [
    {(ix, iz) for ix in (32, 33, 34, 35) for iz in range(-2, 30)},
    {(ix, iz) for ix in range(-1, 32) for iz in (-2, -1, 0, 1)},
    {(ix, iz) for ix in (0, 1) for iz in range(2, 30)},
    {(ix, iz) for ix in range(2, 32) for iz in (28, 29)},
]


def ring_cells(strips):
    out = set()
    for s in strips:
        out |= s
    return out


def cornice():
    steps = []
    grille = {(ix, -1) for ix in range(0, 34)} | {(34, iz) for iz in range(-1, 30)}
    for k, y in enumerate((0, -8)):
        lay = []
        for n, strip in enumerate(RING_A):
            emit(lay, f"ca{k}-{n}", strip, RB, y, PLATE_RECTS, reverse=bool(k),
                 purpose="Corbel courses of the terracotta cornice, laid in staggered strips"
                 if k == 0 and n == 0 else None)
        steps.append(lay)
    frieze = []
    emit(frieze, "fz", grille, RB, -32, GRILLE_RECTS,
         purpose="Ribbed frieze standing in for the foliate terracotta band")
    for n, strip in enumerate(RING_A):
        emit(frieze, f"fzb-{n}", strip - grille, RB, -32, BRICK_RECTS)
    steps.append(frieze)
    for k, y in enumerate((-40, -48)):
        lay = []
        for n, strip in enumerate(RING_B):
            emit(lay, f"cd{k}-{n}", strip, RB, y, PLATE_RECTS, reverse=bool(k),
                 purpose="Crowning double projection of the cornice" if k == 0 and n == 0 else None)
        steps.append(lay)
    cap = []
    allB = ring_cells(RING_B)
    edge = {c for c in allB if c[0] in (-1, 35) or c[1] == -2
            or (c[0] == 34 and c[1] >= 2) or (c[1] == 29 and 2 <= c[0] <= 31)}
    for n, strip in enumerate(RING_B):
        emit(cap, f"cap-{n}", strip - edge, RB, -56, TILE_RECTS,
             purpose="Cap tiles sharpen the cornice silhouette" if n == 0 else None)
        emit(cap, f"capedge-{n}", strip & edge, DRED, -56, TILE_RECTS)
    steps.append(cap)
    return section("brad-cornice",
                   "Heavy projecting terracotta cornice: two corbel courses, a ribbed frieze, "
                   "a crowning double projection and dark cap tiles",
                   steps, {"base": {"at": [0, 8, 0]}})


# ---------------------------------------------------------------- roof -----
def roof():
    """Roof structure.

    Layer 1 spans the wall tops *and* the gallery ring, so the roof is carried by the
    masonry rather than cantilevering off nothing; layer 2 is staggered over the
    gallery only.  The cornice is then attached to this module's `next` anchor.
    """
    inner = {(ix, iz) for ix in range(2, 32) for iz in range(2, 28)} - COURT - CORNER_CELLS
    steps = []
    lay = []
    emit(lay, "rb", FOOTPRINT - COURT, DBG, 0, PLATE_RECTS,
         purpose="One packed bed spans the wall heads and the gallery ring, so the roof "
                 "is carried by the masonry and also beds the cornice")
    steps.append(lay)
    lay2 = []
    emit(lay2, "rd2", inner, DBG, -8, PLATE_RECTS, reverse=True,
         purpose="Staggered second course ties the roof gallery back into the walls")
    steps.append(lay2)

    frame_ring = {c for c in {(ix, iz) for ix in range(4, 30) for iz in range(4, 26)}
                  if c[0] in (4, 29) or c[1] in (4, 25)}
    beams = {(ix, iz) for ix in (9, 10, 15, 16, 21, 22) for iz in range(4, 26)}
    frame = []
    emit(frame, "beam", beams, BLACK, -32, BRICK_RECTS,
         purpose="Two-stud beams span the court and bear on the skylight kerb")
    emit(frame, "kerb", frame_ring - beams, BLACK, -32, BRICK_RECTS)
    steps.append(frame)

    glass = []
    for k in range(11):
        emit(glass, f"sky{k}", {(ix, 4 + 2 * k) for ix in range(4, 30)}
             | {(ix, 5 + 2 * k) for ix in range(4, 30)}, TRANS, -40, PLATE_RECTS,
             purpose="Trans-clear glazing laid in strips so every pane bridges a beam"
             if k == 0 else None)
    steps.append(glass)

    bars = []
    long_bars = {(ix, iz) for ix in (9, 15, 21) for iz in range(4, 26)}
    cross_bars = {(ix, iz) for iz in (8, 13, 18, 23) for ix in range(4, 30)} - long_bars
    emit(bars, "bar", long_bars, BLACK, -48, TILE_RECTS, purpose="Glazing bars")
    emit(bars, "xbar", cross_bars, BLACK, -48, TILE_RECTS)
    steps.append(bars)

    extra = []
    bulk = {(ix, iz) for ix in range(2, 10) for iz in range(26, 28)}
    for c in range(3):
        emit(extra, f"bulk{c}", bulk, DBG, -32 - 24 * c, BRICK_RECTS,
             purpose="Stair bulkhead" if c == 0 else None)
    emit(extra, "bulkcap", bulk, BLACK, -88, PLATE_RECTS, reverse=True)
    for k, (vx, vz) in enumerate(((130, 70), (130, 190), (130, 330), (-430, 70))):
        extra.append(P(f"vent-{k}", "3062b", LBG, [vx, -32, vz]))
        extra.append(P(f"ventc-{k}", "98138", LBG, [vx, -40, vz]))
    steps.append(extra)
    return section("brad-roof",
                   "Roof bed on the wall heads, glazed light-court skylight on a black kerb "
                   "and beams, stair bulkhead and vents",
                   steps, {"base": {"at": [0, 8, 0]}, "next": {"at": [0, 0, 0]}})


# ------------------------------------------------------- interior pieces ---
RING46 = {(a, b) for a in range(4) for b in range(6) if a in (0, 3) or b in (0, 5)}
FULL46 = {(a, b) for a in range(4) for b in range(6)}


def elevator():
    """Open-cage elevator: a 4 x 6 ironwork ring tied together by a plate course per level."""
    steps = []
    for lv in range(10):
        y = -40 - 56 * lv
        lay = [P(f"cage-s{lv}", "19121", BLACK, [40, y, -50]),
               P(f"cage-n{lv}", "19121", BLACK, [40, y, 50], yaw=180),
               P(f"cage-w{lv}", "19121", BLACK, [10, y, 0], yaw=90),
               P(f"cage-e{lv}", "19121", BLACK, [70, y, 0], yaw=-90)]
        if lv == 0:
            lay[0]["purpose"] = "Open ironwork elevator shaft, the signature of the light court"
        if lv == 4:
            emit(lay, "car-floor", FULL46, GOLD, y - 8, PLATE_RECTS, ox=0, oz=-60,
                 purpose="The gilded car floor doubles as this level's tie course")
            lay.append(P("car-w", "19121", GOLD, [30, y - 56, 0], yaw=90))
            lay.append(P("car-e", "19121", GOLD, [50, y - 56, 0], yaw=-90))
            emit(lay, "car-roof", {(a, b) for a in (1, 2) for b in range(1, 5)}, GOLD,
                 y - 64, PLATE_RECTS, ox=0, oz=-60)
            lay.append(P("car-lamp", "3062b", TRANS, [50, y - 88, -10]))
        else:
            emit(lay, f"tie{lv}", RING46, BLACK, y - 8, PLATE_RECTS, ox=0, oz=-60,
                 purpose="Plate course ties the four cage panels into one shaft" if lv == 0 else None)
        steps.append(lay)
    return section("brad-elevator",
                   "Open-cage elevator: ornamental black ironwork shaft, tied every level, "
                   "with a gilded car",
                   steps, {"base": {"at": [0, 8, 0]}})


def stair():
    """Oak stair: eight 16 LDU risers built as interlocking plate layers, not loose columns."""
    import math
    steps = []
    for j in range(17):
        bmin = 0 if j == 0 else 1 + math.ceil(j / 2)
        cells = {(a, b) for a in range(4) for b in range(bmin, 12)}
        lay = []
        emit(lay, f"lay{j}", cells, RB, -8 * j, PLATE_RECTS, ox=0, oz=0,
             purpose="Each plate layer runs from its riser to the landing, so the flight is bonded"
             if j == 0 else None)
        steps.append(lay)
    treads = [P(f"tread-{b}", "2431", DTAN, [40, -16 * (b - 1) - 8, 20 * b + 10])
              for b in range(2, 10)]
    treads.append(P("tread-top", "87079", DTAN, [40, -136, 220]))
    treads.append(P("tread-pod", "87079", DTAN, [40, -8, 20]))
    steps.append(treads)
    return section("brad-stair",
                   "Oak stair with tiled treads rising from the court floor to the first gallery",
                   steps, {"base": {"at": [0, 8, 0]}})


# ------------------------------------------------------ exterior details ---
def fire_escape():
    """Full-height 3rd Street fire escape.

    Local origin sits on the wall face; +X points away from the building and local
    y = 8 is the sidewalk surface.  Landings are two staggered plate layers so every
    piece is bonded, and they start one stud clear of the brickwork to miss the
    arcade corbel and the cornice projections.
    """
    steps = []
    landings = [-128, -240, -352, -464]
    posts = []
    bottom = 8
    for lv, ly in enumerate(landings):
        top = ly + 8                        # underside of this landing
        for tag, pz in (("pa", -50), ("pb", 50)):
            column(posts, f"{tag}{lv}", 70, pz, bottom, bottom - top, BLACK)
        bottom = ly - 8                     # landing is 16 LDU thick
    posts[0]["purpose"] = "Free-standing steel posts carry the fire-escape landings"
    steps.append(posts)

    for lv, ly in enumerate(landings):
        lay = []
        if lv == 0:
            cells = {(a, b) for a in range(1, 5) for b in range(6)}
            rects = [(4, 2, "3020"), (4, 1, "3710"), (2, 1, "3023b"), (1, 1, "3024")]
        else:
            cells = {(a, b) for a in range(1, 4) for b in range(6)}
            rects = LANDING_RECTS
        for k, yy in enumerate((ly, ly - 8)):
            emit(lay, f"land{lv}-{k}", cells, BLACK, yy, rects, rotate=False,
                 reverse=bool(k), ox=0, oz=-60,
                 purpose="Two staggered plate layers bond each landing to both posts"
                 if lv == 0 and k == 0 else None)
        emit(lay, f"grille{lv}", {(1, b) for b in range(1, 5)}, BLACK, ly - 16,
             GRILLE_TILE_RECTS, ox=0, oz=-60)
        steps.append(lay)

    # Guarding.  Ladder 4207a was rejected: its only connectors are underside stud
    # receptacles for flat mounting, so any vertical placement would float.  A joint
    # test (output/joint-test2.plan.json) also showed nothing connects on top of a
    # 3185 lattice, so each panel is base-seated on its own landing rather than
    # stacked into a full-height cage.
    cage = []
    for lv, ly in enumerate(landings):
        cage.append(P(f"cage-{lv}", "3185", BLACK, [70, ly - 56, 0], yaw=90,
                      **({"purpose": "Latticed outboard guard; its four underside "
                                     "receptacles land on the landing's stud row"}
                         if lv == 0 else {})))
    steps.append(cage)
    return section("brad-fire-escape",
                   "Black fire escape on the 3rd Street elevation: posts, grille landings, "
                   "latticed outboard guards",
                   steps, {"base": {"at": [0, 8, 0]}})


def blade_sign():
    pole = [P("foot", "3020", DBG, [0, -8, 0],
              purpose="Kerbside pylon carrying the vertical blade sign")]
    y = -8
    for k in range(6):
        y -= 24
        pole.append(P(f"post-{k}", "3004", BLACK, [0, y, -10]))
    blade = []
    for k in range(7):
        y -= 24
        blade.append(P(f"blade-{k}", "3004", WHITE, [0, y, -10]))
        y -= 8
        blade.append(P(f"line-{k}", "3023b", BLACK, [0, y, -10]))
    blade[0]["purpose"] = ("Pale sign board with dark bands reading as the stacked "
                           "BRADBURY BLDG lettering")
    cap = [P("cap", "3069b", BLACK, [0, y - 8, -10])]
    return section("brad-blade-sign",
                   "Vertical BRADBURY BLDG blade sign on a kerbside pylon",
                   [pole, blade, cap], {"base": {"at": [0, 0, 0]}})


def street_lamp():
    return section("brad-lamp",
                   "Fluted street lamp with a brass collar and a glowing globe",
                   [[P("foot", "3022", DBG, [0, -8, 0],
                       purpose="Plate foot: Support 2 x 2 x 7 needs four studs beneath it"),
                     P("column", "2039", BLACK, [0, -176, 0]),
                     P("collar", "3024", GOLD, [0, -184, 0]),
                     P("shaft", "3062b", BLACK, [0, -208, 0]),
                     P("globe", "3062b", TRANS, [0, -232, 0]),
                     P("finial", "98138", BLACK, [0, -240, 0])]],
                   {"base": {"at": [0, 0, 0]}})


def traffic_signal():
    return section("brad-signal", "Corner traffic signal with a compact three-lens head",
                   [[P("foot", "3022", DBG, [0, -8, 0],
                       purpose="Compact lens stack keeps the signal below the lamps"),
                     P("post", "2039", BLACK, [0, -176, 0]),
                     P("neck", "3024", BLACK, [0, -184, 0]),
                     P("green", "3024", GREEN, [0, -192, 0]),
                     P("amber", "3024", YELLOW, [0, -200, 0]),
                     P("red", "3024", RED, [0, -208, 0]),
                     P("hood", "3070b", BLACK, [0, -216, 0])]],
                   {"base": {"at": [0, 0, 0]}})


def planter():
    tub = [P("tub-a", "3031", DBG, [0, -8, 0], purpose="Sidewalk planter"),
           P("tub-b", "3031", LBG, [0, -16, 0])]
    trunk = [P(f"trunk-{k}", "3062b", RB, [10, -40 - 24 * k, 10]) for k in range(5)]
    leaves = [P("leaf-a", "2417", GREEN, [10, -144, 10],
                purpose="Three layers of Plant Leaves 6 x 5, each turned a quarter, make a real canopy"),
              P("leaf-b", "2417", GREEN, [10, -152, 10], yaw=90),
              P("leaf-c", "2417", GREEN, [10, -160, 10], yaw=180),
              P("crown", "3062b", GREEN, [10, -184, 10])]
    return section("brad-planter", "Sidewalk planter with a small street tree",
                   [tub, trunk, leaves], {"base": {"at": [0, 0, 0]}})


def hydrant():
    return section("brad-hydrant", "Fire hydrant at the kerb",
                   [[P("base", "3062b", RED, [0, -24, 0]),
                     P("body", "3062b", RED, [0, -48, 0]),
                     P("cap", "98138", RED, [0, -56, 0])]],
                   {"base": {"at": [0, 0, 0]}})


# ---------------------------------------------------------------- base -----
def base():
    steps = []
    plates = [P(f"bp-{k}", "91405", DBG, [bx, 0, bz],
                **({"purpose": "Nine 16 x 16 plates form the corner site"} if k == 0 else {}))
              for k, (bx, bz) in enumerate([(x, z) for x in (-320, 0, 320) for z in (-320, 0, 320)])]
    steps.append(plates)

    # ground-plane partition in 20 LDU cells, origin (-480, -480)
    building = {(a, b) for a in range(0, 34) for b in range(18, 48)}
    road_s = {(a, b) for a in range(0, 48) for b in range(0, 12)}
    kerb_s = {(a, 12) for a in range(0, 48)}
    walk_s = {(a, b) for a in range(0, 48) for b in range(13, 18)}
    walk_e = {(a, b) for a in range(34, 39) for b in range(18, 48)}
    kerb_e = {(39, b) for b in range(18, 48)}
    road_e = {(a, b) for a in range(40, 48) for b in range(18, 48)}
    assert not (building & (road_s | kerb_s | walk_s | walk_e | kerb_e | road_e))

    surf = []
    emit(surf, "road-s", road_s, DBG, -8, PLATE_RECTS, ox=-480, oz=-480,
         purpose="Broadway carriageway")
    emit(surf, "road-e", road_e, DBG, -8, PLATE_RECTS, ox=-480, oz=-480)
    emit(surf, "kerb-s", kerb_s, WHITE, -8, PLATE_RECTS, ox=-480, oz=-480,
         purpose="Granite kerb line")
    emit(surf, "kerb-e", kerb_e, WHITE, -8, PLATE_RECTS, ox=-480, oz=-480)
    emit(surf, "walk-s", walk_s, LBG, -8, PLATE_RECTS, ox=-480, oz=-480,
         purpose="Paved sidewalk")
    emit(surf, "walk-e", walk_e, LBG, -8, PLATE_RECTS, ox=-480, oz=-480)
    steps.append(surf)

    marks = []
    emit(marks, "lane", {(a, 5) for a in range(24, 48, 4)} | {(a, 6) for a in range(24, 48, 4)},
         WHITE, -16, TILE_RECTS, ox=-480, oz=-480, purpose="Lane markings")
    emit(marks, "xwalk", {(a, b) for a in range(2, 20, 3) for b in range(0, 11)},
         WHITE, -16, TILE_RECTS, ox=-480, oz=-480)
    steps.append(marks)
    return section("brad-base",
                   "Corner site: carriageway with markings, granite kerb and paved sidewalk "
                   "on nine 16 x 16 plates",
                   steps, {"base": {"at": [0, 8, 0]}})


# --------------------------------------------------------------- scene -----
def scene():
    steps = [[P("site", "brad-base.ldr", DBG, [0, 0, 0], purpose="Street, kerb and sidewalk")]]

    stack = [P("ground", "brad-ground.ldr", TAN, [0, Y_GROUND, 0],
               purpose="Stone ground storey with shopfronts and the Broadway entrance")]
    prev = "ground"
    for k in range(1, 4):
        pid = f"storey-{k}"
        d = {"id": pid, "ref": "brad-storey.ldr", "colour": TAN,
             "attach": {"to": prev, "anchor": "next", "using": "base"}}
        stack.append(d)
        prev = pid
    stack.append({"id": "arcade", "ref": "brad-arcade.ldr", "colour": TAN,
                  "attach": {"to": prev, "anchor": "next", "using": "base"},
                  "purpose": "Top-floor round-arch arcade"})
    stack.append({"id": "roof", "ref": "brad-roof.ldr", "colour": DBG,
                  "attach": {"to": "arcade", "anchor": "next", "using": "base"},
                  "purpose": "Roof bed, skylight and bulkhead"})
    stack.append({"id": "cornice", "ref": "brad-cornice.ldr", "colour": RB,
                  "attach": {"to": "roof", "anchor": "next", "using": "base"}})
    steps.append(stack)

    steps.append([
        P("lift-a", "brad-elevator.ldr", BLACK, [0, -24, 60],
          purpose="Two open-cage elevators stand in the light court"),
        P("lift-b", "brad-elevator.ldr", BLACK, [0, -24, 260]),
        P("stair-1", "brad-stair.ldr", RB, [-140, -24, 140]),
    ])

    steps.append([P("escape", "brad-fire-escape.ldr", BLACK, [X1, -16, 220],
                    purpose="Fire escape on the 3rd Street elevation")])

    steps.append([
        P("sign", "brad-blade-sign.ldr", BLACK, [240, -8, -160],
          purpose="Vertical BRADBURY BLDG sign right on the street corner"),
        P("lamp-a", "brad-lamp.ldr", BLACK, [280, -8, 60]),
        P("lamp-b", "brad-lamp.ldr", BLACK, [-120, -8, -180], yaw=90),
        P("signal", "brad-signal.ldr", BLACK, [280, -8, -200]),
        P("planter-a", "brad-planter.ldr", GREEN, [-420, -8, -180]),
        P("planter-b", "brad-planter.ldr", GREEN, [260, -8, 300]),
        P("hydrant", "brad-hydrant.ldr", RED, [70, -8, -170]),
    ])
    return section("bradbury",
                   "The Bradbury Building, Broadway at 3rd Street, Los Angeles: brick corner block "
                   "with a chamfered corner, round-arch arcade, glazed light court and street furniture",
                   steps)


def cutaway():
    """Review-only variant: ground storey + one gallery, no roof, so the court is visible."""
    steps = [[P("site", "brad-base.ldr", DBG, [0, 0, 0])]]
    steps.append([
        P("ground", "brad-ground.ldr", TAN, [0, Y_GROUND, 0]),
        {"id": "storey-1", "ref": "brad-storey.ldr", "colour": TAN,
         "attach": {"to": "ground", "anchor": "next", "using": "base"}},
    ])
    steps.append([
        P("lift-a", "brad-elevator.ldr", BLACK, [0, -24, 60]),
        P("lift-b", "brad-elevator.ldr", BLACK, [0, -24, 260]),
        P("stair-1", "brad-stair.ldr", RB, [-140, -24, 140]),
    ])
    return section("bradbury-cutaway",
                   "Cutaway review model: ground storey, first gallery, oak stair and both "
                   "open-cage elevators in the light court",
                   steps)


# ---------------------------------------------------------------- main -----
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, default=Path("output/plans"))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    details = [fire_escape(), blade_sign(), street_lamp(), traffic_signal(),
               planter(), hydrant(), elevator(), stair()]
    write(args.outdir / "details.plan.json", details)

    building = [base(), storey("brad-ground", "ground"), storey("brad-storey", "typical"),
                storey("brad-arcade", "arcade"), cornice(), roof()]
    write(args.outdir / "building.plan.json", building, includes=["details.plan.json"])

    write(args.outdir / "scene.plan.json", [scene()], includes=["building.plan.json"])
    write(args.outdir / "cutaway.plan.json", [cutaway()], includes=["building.plan.json"])
    print(args.outdir / "scene.plan.json")


if __name__ == "__main__":
    main()
