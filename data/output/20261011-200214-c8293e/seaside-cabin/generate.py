"""Generator for Tidewater Cabin (seaside cabin with garden).

Writes output/seaside-cabin/cabin.plan.json. Units are LDU; negative Y is up.
Bricks/plates are placed by their TOP face origin (body extends toward +Y):
  course c (0 = plinth) has origin y = -24*(c+1), body y in [-24*(c+1), -24*c].
  plate on top of course c: origin y = -24*(c+1) - 8.

Coordinates: x across the front, z toward the front (sea side, +z), y up (negative).
Footprint: outer x in [-80,80], z in [-100,100]; walls two studs (40 LDU) thick.
Front wall centre z=+80, back z=-80, left x=-60, right x=+60.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).with_name("cabin.plan.json")

# Palette roles (LDraw colour codes)
WOOD = 6        # Brown: weathered wood walls
STONE = 71      # Light bluish grey: plinth and foundation
ROOF = 72       # Dark bluish grey: slate roof
GLASS = 43      # Trans light blue: sea-glass glazing
LAMP = 46       # Trans yellow: lit window
YELLOW = 14     # Yellow lantern
TAN = 19        # Sand path and deck
GREEN = 2       # Planting
WHITE = 15      # White: upper cladding, gable and ceiling trim
DOOR = 4        # Red door
PINK = 5         # Dark pink (catalog: Dark_Pink) planter

placements = []
_ids = {}


def _uid(base):
    n = _ids.get(base, 0)
    _ids[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


def add(step, ref, colour, x, y, z, yaw=0, base="p"):
    step.append({
        "id": _uid(base),
        "ref": ref,
        "colour": colour,
        "at": [x, y, z],
        "yaw": yaw,
    })


def origin_y(course):
    """Top-face origin for a 24 LDU brick course (0 = plinth)."""
    return -24 * (course + 1)


# ---------------------------------------------------------------------------
# Wall filling
# ---------------------------------------------------------------------------
# A wall is described by its axis ('x' runs along the front/back, 'z' along the
# sides), its fixed coordinate, and a start coordinate in studs (-80 or -60).
# Openings are (start_stud, end_stud, courses, glazing_colour_or_None).

def fill_course(step, axis, fixed, start, length_studs, y, colour, gaps, base):
    """Fill one course with 2-stud-thick bricks; 1-stud pieces become pairs of 1x1s."""
    stud = 20
    blocked = set()
    for g in gaps:
        for s in range(g[0], g[1]):
            blocked.add(s)
    s = 0
    while s < length_studs:
        if s in blocked:
            s += 1
            continue
        run = 0
        while s + run < length_studs and (s + run) not in blocked:
            run += 1
        pos = s
        remaining = run
        while remaining > 0:
            take = 4 if remaining >= 4 else (3 if remaining == 3 else (2 if remaining >= 2 else 1))
            seg_start = start + pos * stud  # LDU: start is the wall's first edge in LDU
            centre = seg_start + take * stud / 2
            if take == 4 or take == 3 or take == 2:
                ref = {4: "3001.dat", 3: "3002.dat", 2: "3003.dat"}[take]
                yaw = 0 if axis == "x" else 90
                if axis == "x":
                    add(step, ref, colour, centre, y, fixed, yaw, base)
                else:
                    add(step, ref, colour, fixed, y, centre, yaw, base)
            else:
                # one stud wide: two 1x1 bricks side by side across the 2-stud thickness
                c = seg_start + stud / 2
                for off in (-10, 10):
                    if axis == "x":
                        add(step, "3005.dat", colour, c, y, fixed + off, 0, base)
                    else:
                        add(step, "3005.dat", colour, fixed + off, y, c, 0, base)
            pos += take
            remaining -= take
        s += run


def wall(steps_by_course, axis, fixed, start, length_studs, courses, openings, base, colour=WOOD):
    """openings: list of (start_stud, end_stud, course_set, glazing)."""
    for c in courses:
        step = steps_by_course.setdefault(c, [])
        gaps = [(o[0], o[1]) for o in openings if c in o[2]]
        fill_course(step, axis, fixed, start, length_studs, origin_y(c), colour, gaps, f"{base}-c{c}")
    # glazing: 1x2 plates stacked over each opening, centred in the wall thickness
    for (a, b, cset, glaze) in openings:
        if glaze is None:
            continue
        rows = sorted(cset)
        top = origin_y(rows[-1])          # top face of highest course in the opening
        bottom = origin_y(rows[0]) + 24   # bottom face of lowest course
        n = (bottom - top) // 8
        stud = 20
        centre = start + (a + b) / 2 * stud
        if axis == "x":
            step = steps_by_course.setdefault(("glass", base), [])
            for k in range(n):
                add(step, "3023b.dat", glaze, centre, top + 8 * k, fixed, 0, f"{base}-glass")
        else:
            step = steps_by_course.setdefault(("glass", base), [])
            for k in range(n):
                add(step, "3023b.dat", glaze, fixed, top + 8 * k, centre, 90, f"{base}-glass")


steps = {}

# 1. Plinth: light bluish grey brick grid over the whole footprint (2 studs thick rows)
plinth = []
for zc in (-80, -40, 0, 40, 80):
    for xc in (-40, 40):
        add(plinth, "3001.dat", STONE, xc, origin_y(0), zc, 0, "plinth")
steps["plinth"] = plinth

# 2. Ground walls, courses 1..3
ground_front = [(2, 4, {1, 2}, DOOR),        # red door panel
                (5, 7, {2, 3}, GLASS)]       # window
ground_back = [(1, 3, {2, 3}, GLASS),
               (5, 7, {2, 3}, GLASS)]
ground_left = [(1, 3, {2, 3}, GLASS)]
ground_right = [(2, 4, {2, 3}, GLASS)]
ground_courses = [1, 2, 3]
wall(steps, "x", 80, -80, 8, ground_courses, ground_front, "gf")
wall(steps, "x", -80, -80, 8, ground_courses, ground_back, "gb")
wall(steps, "z", -60, -60, 6, ground_courses, ground_left, "gl")
wall(steps, "z", 60, -60, 6, ground_courses, ground_right, "gr")

# 3. Upper walls, courses 4..6
upper_front = [(2, 4, {4, 5}, GLASS),
               (5, 7, {4, 5}, LAMP)]        # lit room over the door
upper_back = [(3, 5, {4, 5}, GLASS)]
upper_left = [(0, 2, {4, 5}, GLASS)]
upper_right = [(1, 3, {4, 5}, GLASS)]
upper_courses = [4, 5, 6]
wall(steps, "x", 80, -80, 8, upper_courses, upper_front, "uf", WHITE)
wall(steps, "x", -80, -80, 8, upper_courses, upper_back, "ub", WHITE)
wall(steps, "z", -60, -60, 6, upper_courses, upper_left, "ul", WHITE)
wall(steps, "z", 60, -60, 6, upper_courses, upper_right, "ur", WHITE)

# 4. Gable infill at course 7 (front and back), then the roof rows
gable = []
for zc in (80, -80):
    for xc in (-20, 20):
        add(gable, "3003.dat", WHITE, xc, origin_y(7), zc, 0, f"gable-{zc}")
steps["gable"] = gable + steps.get("gable", [])

# Attic ceiling: three 2x4 bricks across the interior, resting on the upper wall tops
ceiling = []
for zc in (-40, 0, 40):
    add(ceiling, "3001.dat", WHITE, 0, origin_y(7), zc, 0, "ceiling")
steps["ceiling"] = ceiling

# Roof: 45-degree slopes, ridge along z. Two rows per side, stepping 40 LDU in x
# and 24 LDU in height. Slope origins are placed by the top face; check renders.
roof = []
roof_z = [(-60, 0), (20, 1), (80, 2)]  # centres in z, length tag
for zc, tag in [(-60, "a"), (20, "b")]:
    add(roof, "3037.dat", ROOF, -60, -192, zc, 90, f"roofL0-{tag}")
    add(roof, "3037.dat", ROOF, -20, -216, zc, 90, f"roofL1-{tag}")
    add(roof, "3037.dat", ROOF, 60, -192, zc, 270, f"roofR0-{tag}")
    add(roof, "3037.dat", ROOF, 20, -216, zc, 270, f"roofR1-{tag}")
# final 40 LDU bay at the front gable
add(roof, "3039.dat", ROOF, -60, -192, 80, 90, "roofL0-c")
add(roof, "3039.dat", ROOF, -20, -216, 80, 90, "roofL1-c")
add(roof, "3039.dat", ROOF, 60, -192, 80, 270, "roofR0-c")
add(roof, "3039.dat", ROOF, 20, -216, 80, 270, "roofR1-c")
steps["roof"] = roof

# 5. Porch deck and garden (ground level sits at y=0)
porch = []
add(porch, "3020.dat", TAN, -40, -32, 120, 0, "deck")
add(porch, "3005.dat", YELLOW, -70, -56, 110, 0, "lantern-l")
add(porch, "3005.dat", YELLOW, -10, -56, 110, 0, "lantern-r")
steps["porch"] = porch

garden = []
for k, zc in enumerate((160, 200, 240)):
    add(garden, "3022.dat", TAN, -20, -8, zc, 0, f"path-{k}")
add(garden, "3003.dat", PINK, -70, -24, 170, 0, "planter-l")
add(garden, "3003.dat", PINK, 30, -24, 170, 0, "planter-r")
add(garden, "3022.dat", GREEN, -70, -32, 170, 0, "plant-l")
add(garden, "3022.dat", GREEN, 30, -32, 170, 0, "plant-r")
steps["garden"] = garden

# Assemble steps in build order
glass_keys = [k for k in steps if isinstance(k, tuple) and k[0] == 'glass']
# Courses are stored by number; flatten them in order and keep one step per course.
plan_steps = []
for key in ["plinth", 1, 2, 3, 4, 5, 6]:
    if key in steps:
        plan_steps.append(steps[key])
plan_steps.append(steps["gable"])
plan_steps.append(steps["ceiling"])
plan_steps.append(steps["roof"])
for k in glass_keys:
    plan_steps.append(steps[k])
plan_steps.append(steps["porch"])
plan_steps.append(steps["garden"])

plan = {
    "version": 1,
    "author": "LDraw Nova builder agent",
    "sections": [{
        "name": "cabin.ldr",
        "description": "Tidewater Cabin: a seaside timber cabin with a sandy garden",
        "steps": plan_steps,
    }],
}

OUT.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
print(f"wrote {OUT} with {sum(len(s) for s in plan_steps)} placements in {len(plan_steps)} steps")
