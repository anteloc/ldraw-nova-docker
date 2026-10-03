"""Generate Willowbank Cottage: a large two-volume cottage and a vegetable field.

Run from the repository root:

  .venv/bin/python output/garden-cottage/generate.py

Then:

  ./ldraw-agent build output/garden-cottage/scene.plan.json \
      --output output/garden-cottage/willowbank-cottage.mpd \
      --detail summary --report output/garden-cottage/build.json

Authoring layer is ldraw_tools.architecture: X/Z in studs, h in LDU upwards,
modules use bottom Y=0 and face -Z. Part heights below were measured with
`ldraw-agent part` against the installed library (bounds, not names).
"""
from __future__ import annotations

import json
from pathlib import Path

from ldraw_tools.architecture import (
    Module, gable, porch, tree, bench, planter, stairs, fence, slab, line,
    window4, door4, attach_roof,
)
from ldraw_tools.common import atomic_write

OUT = Path(__file__).resolve().parent

# Palette (LDraw codes, verified against the installed LDConfig).
TAN, WHITE, DGRN, RDBR, DTAN, GRN, BGRN = 19, 15, 288, 70, 28, 2, 10
ORANGE, YELLOW, RED, DPINK, GLASS = 25, 14, 4, 5, 43


def paved_path(m, x0, z0, w, d, c=TAN, h=8):
    """Tile a path run on a one-stud lattice; union overlapping runs."""
    grid = getattr(m, "_paved", set())
    for x in range(x0, x0 + w):
        for z in range(z0, z0 + d):
            if (x, z) in grid:
                continue
            m.add("3070b", c, x + .5, h, z + .5)
            grid.add((x, z))
    m._paved = grid


def hall_shell():
    """20x14 two-storey shell, per-row front windows, door at X=+2."""
    w, d, rows = 20, 14, 12
    m = Module("hall-shell",
               "20 by 14 stud two-storey shell with reserved door/window openings "
               "and removable roof interface")
    slab(m, -w/2, -d/2, w, d, 8, RDBR)
    front_rows = [(1, [-8, -4, 8]), (7, [-6, -2, 2, 6])]
    side_rows = [(1, [-2]), (7, [-2])]
    back_rows = [(1, [-5, 3]), (7, [-5, 3])]
    door_cx, door_w = 2, 4
    openings = []
    for r0, xs in front_rows:
        for x in xs:
            openings.append(("front", x, 4, r0, r0 + 2, "window"))
    for r0, xs in side_rows:
        for x in xs:
            openings.append(("left", x, 4, r0, r0 + 2, "window"))
            openings.append(("right", x, 4, r0, r0 + 2, "window"))
    for r0, xs in back_rows:
        for x in xs:
            openings.append(("back", x, 4, r0, r0 + 2, "window"))
    openings.append(("front", door_cx, door_w, 0, 5, "door"))
    by_side = {s: [] for s in ("front", "back", "left", "right")}
    for o in openings:
        by_side[o[0]].append(o[1:])
    for s, holes in by_side.items():
        width = w if s in ("front", "back") else d - 2
        lower = -width/2
        for a in holes:
            if a[0] - a[1]/2 < lower or a[0] + a[1]/2 > lower + width:
                raise ValueError(f"hall opening outside {s}")
        for i, a in enumerate(holes):
            for b in holes[i + 1:]:
                if (max(a[2], b[2]) <= min(a[3], b[3]) and
                        min(a[0] + a[1]/2, b[0] + b[1]/2) >
                        max(a[0] - a[1]/2, b[0] - b[1]/2)):
                    raise ValueError(f"overlapping hall opening in {s}")
    for row in range(rows):
        m.step()
        for s, holes in by_side.items():
            n = w if s in ("front", "back") else d - 2
            lower = -n/2
            blocked = {i for i in range(n)
                       if any(r0 <= row <= r1 and cx - width/2 <= lower + i < cx + width/2
                              for cx, width, r0, r1, _ in holes)}
            i = 0
            while i < n:
                if i in blocked:
                    i += 1
                    continue
                end = i + 1
                while end < n and end not in blocked:
                    end += 1
                colour = DTAN if row == 0 else TAN  # stone plinth course
                x = lower + i if s in ("front", "back") else (-w/2 + .5 if s == "left" else w/2 - .5)
                z = (-d/2 + .5 if s == "front" else d/2 - .5) if s in ("front", "back") else lower + i
                axis = "x" if s in ("front", "back") else "z"
                line(m, x, z, end - i, 8 + (row + 1) * 24, colour, axis=axis,
                     bond=bool(row % 2))
                i = end
    m.step()
    for s, holes in by_side.items():
        for centre, width, r0, _, kind in holes:
            x = centre if s in ("front", "back") else (-w/2 + .5 if s == "left" else w/2 - .5)
            z = (-d/2 + .5 if s == "front" else d/2 - .5) if s in ("front", "back") else centre
            yaw = {"front": 0, "back": 180, "left": 90, "right": -90}[s]
            if kind == "door":
                if centre == door_cx and s == "front":
                    m.add(entry_door(), WHITE, x, 8 + 24*r0, z, yaw=yaw)
                else:
                    m.add(door4(WHITE, RDBR), WHITE, x, 8 + 24*r0, z, yaw=yaw)
            else:
                m.add(window4(WHITE, GLASS), WHITE, x, 8 + 24*r0, z, yaw=yaw)
    top = 8 + rows * 24
    m.step()
    ring_top(m, w, d, top + 8, WHITE)
    m.anchor("roof", h=top + 8).anchor("doorstep", door_cx, 8, -d/2)
    return m


def ring_top(m, w, d, h, c):
    line(m, -w/2, -d/2 + .5, w, h, c, plate=True)
    line(m, -w/2, d/2 - .5, w, h, c, plate=True)
    line(m, -w/2 + .5, -d/2 + 1, d - 2, h, c, axis="z", plate=True)
    line(m, w/2 - .5, -d/2 + 1, d - 2, h, c, axis="z", plate=True)


def entry_door(trim=WHITE):
    """Four-stud glazed entrance with trans light blue glass; bottom Y=0, 144 LDU."""
    m = Module("entry-door",
               "Four-stud glazed entrance with trans light blue glass; bottom Y=0, height 144 LDU; front -Z")
    m.add("60596", trim, h=144)
    m.add("60797c01", trim, -1.6, 144, .25)
    return m


def wing_shell():
    """10x10 one-storey kitchen wing; back door to the field, windows on both sides."""
    w, d, rows = 10, 10, 6
    m = Module("wing-shell",
               "10 by 10 stud kitchen wing shell with back door and side windows; "
               "removable roof interface")
    slab(m, -w/2, -d/2, w, d, 8, RDBR)
    openings = [
        ("back", -2, 4, 0, 5, "door"),
        ("back", 2, 4, 1, 3, "window"),
        ("left", 1, 4, 1, 3, "window"),
        ("right", 1, 4, 1, 3, "window"),
    ]
    by_side = {s: [] for s in ("front", "back", "left", "right")}
    for o in openings:
        by_side[o[0]].append(o[1:])
    for s, holes in by_side.items():
        width = w if s in ("front", "back") else d - 2
        lower = -width/2
        for a in holes:
            if a[0] - a[1]/2 < lower or a[0] + a[1]/2 > lower + width:
                raise ValueError(f"wing opening outside {s}")
    for row in range(rows):
        m.step()
        for s, holes in by_side.items():
            n = w if s in ("front", "back") else d - 2
            lower = -n/2
            blocked = {i for i in range(n)
                       if any(r0 <= row <= r1 and cx - width/2 <= lower + i < cx + width/2
                              for cx, width, r0, r1, _ in holes)}
            i = 0
            while i < n:
                if i in blocked:
                    i += 1
                    continue
                end = i + 1
                while end < n and end not in blocked:
                    end += 1
                colour = DTAN if row == 0 else TAN
                x = lower + i if s in ("front", "back") else (-w/2 + .5 if s == "left" else w/2 - .5)
                z = (-d/2 + .5 if s == "front" else d/2 - .5) if s in ("front", "back") else lower + i
                axis = "x" if s in ("front", "back") else "z"
                line(m, x, z, end - i, 8 + (row + 1) * 24, colour, axis=axis,
                     bond=bool(row % 2))
                i = end
    m.step()
    for centre, width, r0, _, kind in by_side["back"]:
        if kind == "door":
            m.add(door4(WHITE, RDBR), WHITE, centre, 8 + 24*r0, d/2 - .5, yaw=180)
        else:
            m.add(window4(WHITE, GLASS), WHITE, centre, 8 + 24*r0, d/2 - .5, yaw=180)
    for centre, width, r0, _, _ in by_side["left"]:
        m.add(window4(WHITE, GLASS), WHITE, -w/2 + .5, 8 + 24*r0, centre, yaw=90)
    for centre, width, r0, _, _ in by_side["right"]:
        m.add(window4(WHITE, GLASS), WHITE, w/2 - .5, 8 + 24*r0, centre, yaw=-90)
    top = 8 + rows * 24
    m.step()
    ring_top(m, w, d, top + 8, WHITE)
    m.anchor("roof", h=top + 8)
    return m


def chimney():
    m = Module("chimney", "Stone chimney for the hall ridge; base Y=0")
    for i in range(3):
        m.add("3003", DTAN, h=24 * (i + 1))
    m.add("3022", WHITE, h=80)
    return m


# Field geometry: 5 beds of 4 studs, z cells 13..20, raised one plate.
BEDS = [(-14, 0), (-8, 1), (-2, 2), (4, 3), (10, 4)]
FZ0, FZD = 13, 8


def garden_field():
    m = Module("garden-field",
               "Fenced kitchen garden: five raised soil beds of growing vegetables, "
               "a vine trellis, and a gate at the path")
    # Bed bases: dark tan 2x2 tile slabs (tile-on-tile, no stud clash);
    # tilled 1x1 tile surface one plate higher, z cells 14..19.
    for x0, _ in BEDS:
        for dx in (1, 3):
            for dz in (15, 19):
                m.add("3068b", DTAN, x0 + dx, 8, dz,
                      purpose="soil bed base tile")
        for x in range(x0, x0 + 4):
            for z in range(FZ0 + 1, FZ0 + FZD - 1):
                m.add("3070b", DTAN, x + .5, 16, z + .5,
                      purpose="tilled soil tile")
    C = m.add
    # Bed 1: pumpkin patch.
    for x, z in ((-13.5, 15.5), (-11.5, 15.5), (-13.5, 19.5), (-11.5, 19.5)):
        C("51270", ORANGE, x, 48, z, purpose="pumpkin")
    C("3742", YELLOW, -12.5, 18, 14.5)
    C("3742", RED, -11.5, 18, 19.5)
    C("3742", YELLOW, -13.5, 18, 17.5)
    # Bed 2: carrots with two cabbages.
    for x, z in ((-7, 15), (-6, 15), (-5, 15), (-7, 19), (-6, 19), (-5, 19)):
        C("37681", ORANGE, x, 48, z, purpose="root vegetable")
    C("6255", BGRN, -7, 32, 17, purpose="cabbage")
    C("6255", BGRN, -5, 32, 17, purpose="cabbage")
    # Bed 3: leafy greens.
    C("2423", DGRN, -1, 24, 14.5)
    C("2423", DGRN, 0, 24, 14.5)
    C("2423", BGRN, -1, 24, 18.5)
    C("2423", BGRN, 0, 24, 18.5)
    C("2417", BGRN, -0.5, 24, 16.5, purpose="leafy accent")
    # Bed 4: flowering plants and grass.
    C("4727", DPINK, 5, 40, 14.5)
    C("4727", DPINK, 6, 40, 18.5)
    C("3742", YELLOW, 5, 18, 17.5)
    C("3742", RED, 6, 18, 16)
    C("3742", DPINK, 4.5, 18, 19.5)
    for x, z in ((7, 17.5), (4.5, 19.5)):
        C("15279", GRN, x, 16, z)
    # Bed 5: mixed vegetables.
    C("2423", DGRN, 11, 24, 14.5)
    C("2423", BGRN, 12, 24, 18.5)
    C("2423", DGRN, 11, 24, 18.5)
    C("7264", BGRN, 12, 27.2, 14.5, purpose="long-leaf plant")
    C("3742", YELLOW, 11, 18, 17)
    C("3742", RED, 12, 18, 16.5)
    for x, z in ((10.5, 19.5), (13, 19.5)):
        C("15279", GRN, x, 16, z)
    # Vine trellis: two lattice tiers with a draping vine.
    for x in (-6, -2):
        C("3633", WHITE, x, 8, 21, purpose="trellis lattice lower")
        C("3633", WHITE, x, 32, 21, purpose="trellis lattice upper")
    C("16981", BGRN, 6, 56, 19, purpose="draping vine along trellis top")
    C("73828", DGRN, -2, 32, 20.5, purpose="thorn vine on lower tier")
    # Fence perimeter; the 3-stud gap between the front fence post (X=11)
    # and the right fence post (X=14) is the gate opening at the path.
    m.add(fence(25, RDBR), RDBR, -1, 0, 12, purpose="front fence to the gate")
    m.add(fence(27, RDBR), RDBR, 0, 0, 22, purpose="back fence")
    m.add(fence(9, RDBR), RDBR, -14, 0, 17.5, yaw=90,
          purpose="left fence between front and back rails")
    m.add(fence(9, RDBR), RDBR, 14, 0, 17.5, yaw=90,
          purpose="right fence between front and back rails")
    return m


def build_scene():
    m = Module("willowbank-scene",
               "Willowbank Cottage: two-storey hall with dormer and chimney, kitchen "
               "wing, porch, and a fenced vegetable field at the back")
    m.add("4186", GRN, id="site",
          purpose="48x48 grass baseplate; reserve footprints before laying paths")
    hall = hall_shell()
    m.add(hall, TAN, 0, 0, -7, id="hall")
    m.add(gable("hall-roof", 22, 14, roof=DGRN, gable_colour=DGRN, dormer=True),
          DGRN, id="hall-roof",
          attach={"to": "hall", "anchor": "roof", "using": "base"})
    wing = wing_shell()
    m.add(wing, TAN, -5, 0, 6, id="wing")
    m.add(gable("wing-roof", 12, 10, roof=DGRN, gable_colour=DGRN),
          DGRN, id="wing-roof",
          attach={"to": "wing", "anchor": "roof", "using": "base"})
    m.add(porch(w=8, trim=WHITE, roof=DGRN), WHITE, 2, 0, -16, id="entry-porch",
          purpose="Rear edge meets the hall wall face; four-stud entry remains clear")
    m.add(stairs(4, 1), 71, 2, 0, -18.5, id="entry-stairs")
    m.add(chimney(), DTAN, 5, 472, -7, id="ridge-chimney",
          purpose="Sits on the hall ridge tiles at the measured ridge height")
    # Paths: front to the steps, east connector (clearing the step cells
    # X=0..3), garden path through the gate opening (stops before the beds).
    paved_path(m, -2, -24, 4, 5)
    paved_path(m, -2, -20, 2, 2)
    paved_path(m, 4, -20, 10, 2)
    paved_path(m, 12, -18, 2, 30)
    # Garden.
    m.add(garden_field(), 16, 0, 0, 0, id="garden-field")
    # Landscaping.
    m.add(tree(), 2, -16, 0, -19, purpose="frames the front-left corner")
    m.add(tree(), 2, 19, 0, 15, purpose="far right of the field")
    m.add(bench(), RDBR, 10, 0, -16, purpose="faces the front path")
    m.add(planter(DPINK), DPINK, -4, 0, -15, purpose="flanks the steps")
    return m


def main():
    scene = build_scene()
    plan = scene.plan()
    # Order: main scene first (already), then shells, roofs, details, garden.
    order = ["willowbank-scene", "hall-shell", "hall-roof", "wing-shell",
             "wing-roof", "entry-door", "window4-15-43",
             "door4-15-70-traditional", "porch-15-288-8-4-144", "stairs-4-1",
             "chimney", "garden-field", "gate3",
             "fence-26-70", "fence-28-70", "fence-10-70",
             "leaf-tree-288-5", "bench-70", "flower-box-5"]
    sections = {s["name"][:-4]: s for s in plan["sections"]}
    ordered = [sections[k] for k in order if k in sections]
    for name, s in sections.items():
        if not any(s is o for o in ordered):
            ordered.append(s)
    plan["sections"] = ordered
    out = OUT / "scene.plan.json"
    atomic_write(out, json.dumps(plan, indent=1) + "\n")
    total = sum(len(st) for s in plan["sections"] for st in s["steps"])
    print(f"wrote {out}: {len(plan['sections'])} sections, "
          f"{total} physical placements")


if __name__ == "__main__":
    main()
