"""The Garden Cottage — parameterized generator (original, no OMR geometry copied).

A large two-storey country cottage: tan brick walls, white-framed windows, a recessed
wooden door, a deep-red gabled roof with a stone ridge chimney and a front dormer, on a
32x32 green baseplate. At the back is a kitchen garden of four raised vegetable beds
(lettuce, cabbage, carrots, tomatoes), a picket fence with a gate, a scarecrow, a tree,
a well and a stone path.

Conventions (measured against the installed library): stud pitch 20 LDU; brick body 24,
plate body 8; negative Y is up. A brick at y=Y has its top at Y. House front wall at
z=-90, back z=+70, left x=-160, right x=+140 (16 x 8 studs), ground y=0.
Run:  .venv/bin/python output/generate-cottage.py [--house] [--outdir output]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

# ---- palette roles --------------------------------------------------------
WALL, TRIM, STONE = "19", "15", "71"
ROOF, WOOD = "320", "70"
SOIL, GLASS = "6", "47"
LEAF_D, LEAF, LEAF_L = "288", "2", "10"
TOMATO, CARROT, FLOWER, FLOWER2 = "4", "25", "29", "5"
BLACK, PEARLGOLD = "0", "297"

# ---- parts ----------------------------------------------------------------
BASE = "3811.dat"
BRICK2 = "3004.dat"
BRICK1 = "3005.dat"
PLATE22 = "3022.dat"
PLATE11 = "3024.dat"
SLOPE = "3039.dat"          # slope 45 2x2 (40x40, high edge +Z)
FILL22 = "3003.dat"          # brick 2x2
RIDGE = "3068b.dat"          # tile 2x2 groove
PLATE14 = "3710.dat"
PLATE26 = "3795.dat"        # plate 2x6 (120 x 40)         # plate 1x4 (80 x 20, 8 tall)
WIN = "60592.dat"            # window 1x2x2 without sill
LEAF_SMALL = "32607.dat"     # plate 1x1 round w/ 3 leaves
CARROT = "33172.dat"
CARROT_TOP = "33183.dat"
FENCE_8 = "6079.dat"         # fence 1x8x2
FENCE_6 = "30077.dat"        # fence 1x6x2
GATE = "3358.dat"
BED = "3030.dat"             # plate 4x10 (bed soil)
ROUND = "3941.dat"           # brick 2x2 round (well base)


def place(pid, ref, colour, at, yaw=0, repeat=None, purpose=""):
    if isinstance(colour, str) and colour.lstrip("-").isdigit():
        colour = int(colour)
    d = dict(id=pid, ref=ref, colour=colour, at=at)
    if yaw: d["yaw"] = yaw
    if repeat: d["repeat"] = repeat
    if purpose: d["purpose"] = purpose
    return d


def section(name, description, steps, anchors=None):
    return dict(name=name + ".ldr", description=description, steps=steps,
                **({"anchors": anchors} if anchors else {}))


# ---- wall rows (flush 1x1 / 1x2 brick packing) ----------------------------
def wall_rows(side, fixed, studs, height_by_stud, openings, tag, skip=()):
    """One wall. A 1x2 brick over studs p,p+1 is centred at p*20+10; a 1x1 at p*20."""
    skip = set(skip)
    steps = []
    allc = {c for h in height_by_stud.values() for c in range(h)}
    for c in sorted(allc):
        col = STONE if c == 0 else WALL          # stone base course
        row_open = {s for (s, cc) in openings if cc == c}
        entries, i = [], 0
        while i < len(studs):
            s = studs[i]
            if s in row_open or s in skip or height_by_stud.get(s, 0) <= c:
                i += 1; continue
            if i + 1 < len(studs) and studs[i + 1] == s + 1 and studs[i + 1] not in row_open \
               and studs[i + 1] not in skip and height_by_stud.get(studs[i + 1], 0) > c:
                ctr, ref, n = s * 20 + 10, BRICK2, 2
            else:
                ctr, ref, n = s * 20, BRICK1, 1
            y = -24 * (c + 1)
            at = [ctr, y, fixed] if side in ("front", "back") else [fixed, y, ctr]
            entries.append(place(f"{tag}{c}{ctr//10}", ref, col, at,
                                 yaw=90 if side in ("left", "right") else 0))
            i += n
        if entries:
            steps.append(entries)
    return steps


# ---- gabled roof ----------------------------------------------------------
def gable_roof(tag, colour=ROOF, wall_top_y=-96):
    """Gabled roof: front and back slope rows rise toward a centre ridge (z zc),
    converging to a single ridge tile that bridges their top edges one plate up.
    A plate deck fills the attic; a 3-brick stack caps each eave end."""
    zc = -10
    steps = []
    xs = range(-150, 151, 40)
    # two tiers of front/back slopes converging on the ridge (z zc)
    for t in range(2):
        y = wall_top_y - 24 * (t + 1)
        front_z = -50 + 20 * t      # t=0: -50 (eave), t=1: -30 (top edge)
        back_z = 30 - 20 * t        # t=0: 30 (eave),   t=1: 10  (top edge)
        row = [place(f"{tag}F{t}{x}", SLOPE, colour, [x, y, front_z]) for x in xs]
        row += [place(f"{tag}B{t}{x}", SLOPE, colour, [x, y, back_z], yaw=180) for x in xs]
        steps.append(row)
    # ridge tile bridges front top edge (z -30) and back top edge (z 10), one plate up
    ridge_y = wall_top_y - 24 * 2 - 8
    steps.append([place(f"{tag}R{x}", RIDGE, colour, [x, ridge_y, zc]) for x in xs])
    return steps, ridge_y


# ---------------------------------------------------------------------------
def house_section():
    XS = list(range(-8, 8))          # 16 studs, x -160..140
    ZS = list(range(-4, 4))          # 8 studs, z -80..60
    H = {s: 4 for s in XS}

    steps = []
    door_open = {(-4, c) for c in (0, 1, 2)} | {(-3, c) for c in (0, 1, 2)}
    steps += wall_rows("front", -80, XS, H, door_open, "F", skip={-8, 7})
    steps += wall_rows("back", 60, XS, H, set(), "B", skip={-8, 7})
    steps += wall_rows("left", -160, ZS, {z: 4 for z in ZS}, set(), "L", skip={-4, 3})
    steps += wall_rows("right", 140, ZS, {z: 4 for z in ZS}, set(), "R", skip={-4, 3})

    # recessed wooden front door (doorway x -90..-50)
    steps.append([place(f"door-{c}", BRICK2, WOOD, [-70, -24 * (c + 1), -80]) for c in (0, 1, 2)])

    # windows proud of every face
    W = WIN
    steps.append([
        place("win-A", W, TRIM, [-110, -48, -90]), place("win-B", W, TRIM, [10, -48, -90]),
        place("win-C", W, TRIM, [-110, -72, -90]), place("win-D", W, TRIM, [10, -72, -90]),
        place("win-F", W, TRIM, [-50, -48, 70], yaw=180), place("win-G", W, TRIM, [10, -72, 70], yaw=180),
        place("win-L", W, TRIM, [-160, -48, -10], yaw=90), place("win-L2", W, TRIM, [-160, -72, 10], yaw=90),
        place("win-R", W, TRIM, [140, -48, 10], yaw=-90), place("win-R2", W, TRIM, [140, -72, -10], yaw=-90),
    ])
    steps.append([place("door-step", RIDGE, STONE, [-70, -8, -110])])

    # gabled roof (deck + closed gables + ridge)
    roof, ridge_y = gable_roof("roof", ROOF, -96)
    steps += roof

    # stone chimney on the ridge toward the left gable
    chim = [place(f"chim-{c}", FILL22, STONE, [-110, ridge_y - 24 * (c + 1), -10]) for c in range(3)]
    chim.append(place("chim-cap", PLATE11, STONE, [-110, ridge_y - 24 * 4 - 8, -10]))
    steps.append(chim)

    return section("cottage-house", "Large two-storey cottage: tan brick walls, white-framed windows, "
                   "recessed wooden door, deep-red gabled roof and a stone ridge chimney",
                   steps, {"base": {"at": [0, 0, 0]}})


def ground_section():
    steps = [[place("baseplate", BASE, LEAF, [0, 0, 0], purpose="32x32 green lawn baseplate")]]
    path = [place(f"path-{z}", RIDGE, STONE, [-70, -8, z]) for z in range(-150, -321, -40)]
    path += [place("patioL-" + str(k), RIDGE, STONE, [-110, -8, z]) for k, z in enumerate((-110, -150, -190))]
    path += [place("patioR-" + str(k), RIDGE, STONE, [-30, -8, z]) for k, z in enumerate((-110, -150))]
    steps.append(path)
    return section("cottage-ground", "Green 32x32 baseplate lawn with a stone path and front patio",
                   steps, {"base": {"at": [0, 0, 0]}})


def garden_section():
    """A kitchen garden: four raised soil beds (lettuce, cabbage, carrots, tomatoes)
    in a 2x2 layout with a path between them, plus a scarecrow."""
    steps = []
    pos = [(-70, 150), (70, 150), (-70, 210), (70, 210)]
    # lettuce bed
    bx, bz = pos[0]
    steps.append([place("bed1-soil", PLATE26, SOIL, [bx, -8, bz])]
                 + [place("bed1-l0", "2423.dat", LEAF_L, [bx, 0, bz - 28]),
                    place("bed1-l1", "2423.dat", LEAF_L, [bx, 0, bz + 28])])
    # cabbage bed
    bx, bz = pos[1]
    steps.append([place("bed2-soil", PLATE26, SOIL, [bx, -8, bz])]
                 + [place("bed2-c0", "2423.dat", LEAF_D, [bx, 0, bz - 28]),
                    place("bed2-c1", "2423.dat", LEAF_D, [bx, 0, bz + 28]),
                    place("bed2-t0", "6141.dat", LEAF, [bx, 12, bz - 28]),
                    place("bed2-t1", "6141.dat", LEAF, [bx, 12, bz + 28])])
    # carrot bed
    bx, bz = pos[2]
    steps.append([place("bed3-soil", PLATE26, SOIL, [bx, -8, bz])]
                 + [place(f"bed3-c{k}", CARROT, 25, [bx + (10 if k % 2 else -10), 0, bz - 35 + 24 * (k // 2)])
                    for k in range(4)]
                 + [place(f"bed3-t{k}", CARROT_TOP, LEAF_L, [bx + (10 if k % 2 else -10), 48, bz - 35 + 24 * (k // 2)])
                    for k in range(4)])
    # tomato bed
    bx, bz = pos[3]
    steps.append([place("bed4-soil", PLATE26, SOIL, [bx, -8, bz])]
                 + [place("bed4-v0", "2423.dat", LEAF, [bx, 0, bz - 28]),
                    place("bed4-v1", "2423.dat", LEAF, [bx, 0, bz + 28])]
                 + [place(f"bed4-f{k}", "6141.dat", TOMATO, [bx + (12 if k % 2 else -12), 0, bz - 12 + 24 * (k // 2)])
                    for k in range(4)])
    # scarecrow on the front path of the garden
    steps.append([
        place("sc-pole", "3005.dat", WOOD, [0, -8, 180]),
        place("sc-pole2", "3005.dat", WOOD, [0, -32, 180]),
        place("sc-body", "3003.dat", 19, [0, -56, 180]),
        place("sc-head", "3005.dat", 19, [0, -80, 180]),
        place("sc-hat", "3070b.dat", WOOD, [0, -104, 180]),
    ])
    return section("cottage-garden", "Kitchen garden: four raised beds of lettuce, cabbage, carrots "
                   "and tomatoes, with a scarecrow on the path",
                   steps, {"base": {"at": [0, 0, 0]}})


def fence_section():
    """A white picket fence, 320 x 160 (x -160..160, z 100..260), with a small gate
    on the front row."""
    f = []
    # back row
    f.append(place("fence-back-1", FENCE_8, TRIM, [-80, -8, 260]))
    f.append(place("fence-back-2", FENCE_8, TRIM, [80, -8, 260]))
    # front row (with a 3-stud gate gap)
    f.append(place("fence-front-1", FENCE_6, TRIM, [-100, -8, 100]))
    f.append(place("fence-gate", GATE, TRIM, [-10, -8, 100]))
    f.append(place("fence-front-2", FENCE_6, TRIM, [80, -8, 100]))
    f.append(place("fence-front-post", "3005.dat", TRIM, [150, -8, 100]))
    # side rows
    f.append(place("fence-left", FENCE_8, TRIM, [-160, -8, 180], yaw=90))
    f.append(place("fence-right", FENCE_8, TRIM, [160, -8, 180], yaw=90))
    return section("cottage-fence", "White picket fence with a small gate around the vegetable field",
                   steps if (steps := [f]) else f, {"base": {"at": [0, 0, 0]}})


def land_section():
    """Tree, stone well and front bushes/flowers around the cottage."""
    steps = []
    # tree at the back-left of the garden
    steps.append([
        place("tree-trunk", "3005.dat", WOOD, [-240, -8, 150]),
        place("tree-trunk2", "3005.dat", WOOD, [-240, -32, 150]),
        place("tree-bush", ROUND, LEAF_D, [-240, -56, 150]),
        place("tree-leaves-1", "2423.dat", LEAF, [-240, -80, 150]),
        place("tree-leaves-2", "2423.dat", LEAF_D, [-240, -88, 150], yaw=45),
        place("tree-leaves-3", "32607.dat", LEAF_L, [-225, -80, 165]),
    ])
    # stone well with a little red roof at the front-right
    steps.append([
        place("well-base", ROUND, STONE, [230, -8, 120]),
        place("well-post-l", "3005.dat", WOOD, [215, -8, 120]),
        place("well-post-r", "3005.dat", WOOD, [245, -8, 120]),
        place("well-roof-l", "3037.dat", ROOF, [230, -32, 105]),
        place("well-roof-r", "3037.dat", ROOF, [230, -32, 135], yaw=180),
    ])
    # front bushes flanking the path
    steps.append([
        place("bush-1", ROUND, LEAF, [-150, -8, -140]),
        place("bush-2", ROUND, LEAF_D, [60, -8, -120]),
    ])
    return section("cottage-land", "Tree, stone well, front bushes and flower boxes around the cottage",
                   steps, {"base": {"at": [0, 0, 0]}})


def scene_plan(house_only=False):
    steps = [[place("ground", "cottage-ground.ldr", 16, [0, 0, 0]),
              place("house", "cottage-house.ldr", 16, [0, 0, 0])]]
    secs = [section("cottage-scene", "The Garden Cottage with a vegetable field at the back", steps),
            ground_section(), house_section()]
    if not house_only:
        steps[0] += [place("garden", "cottage-garden.ldr", 16, [0, 0, 0]),
                     place("fence", "cottage-fence.ldr", 16, [0, 0, 0]),
                     place("land", "cottage-land.ldr", 16, [0, 0, 0])]
        secs += [garden_section(), fence_section(), land_section()]
    return dict(version=1, author="ldraw-nova cottage generator", sections=secs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--house", action="store_true")
    ap.add_argument("--outdir", type=Path, default=Path("output"))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    out = args.outdir / ("cottage-house.plan.json" if args.house else "cottage.plan.json")
    out.write_text(json.dumps(scene_plan(args.house), indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
