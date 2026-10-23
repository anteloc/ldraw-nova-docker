"""Generate the sideways-stud lighthouse plan.

Coordinates: LDU, negative Y is up. Bricks use their top face as origin and
extend toward +Y (down). Ground (Y=0) is the bottom of the plinth.

Tower walls are 67329 bricks (studs on three sides). Each wall is yawed so its
studded -Z face points outward. Four walls per layer form the square tower
section; a 2x2 core and 1x1 corner stacks fill the interior and corners.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).with_name("lighthouse.plan.json")

LAYERS = 4                   # tower storeys
WALL_H = 40                  # 67329 body height (5 plates)
PLINTH_LAYERS = 2            # 2x4 bricks, 24 each
WHITE, RED, GLASS, DARK, TAN, YELLOW = 15, 4, 47, 72, 19, 14
BLACK = 0

steps = []        # list of steps; each step is a list of placements
counter = {"n": 0}


def add(step, pid, ref, colour, at, yaw=None, purpose=None):
    p = {"id": pid, "ref": ref, "colour": colour, "at": at}
    if yaw is not None:
        p["yaw"] = yaw
    if purpose:
        p["purpose"] = purpose
    step.append(p)


def fmt(v):
    return float(v)


# ---- plinth: two courses of 2x4 bricks (80 x 40 each), 2 per course ----
plinth_steps = []
for layer in range(PLINTH_LAYERS):
    y = -24 - 24 * layer
    step = []
    for z, label in ((-20, "north"), (20, "south")):
        add(step, f"plinth-{layer}-{label}", "3001.dat", TAN, [0, y, z],
            purpose="Brick 2 x 4 (rock plinth course)")
    plinth_steps.append(step)
steps.extend(plinth_steps)

# ---- tower storeys ----
FACES = [
    # name, origin direction (outward), yaw so local -Z points outward
    ("south", (0, 0, 30), 180),
    ("north", (0, 0, -30), 0),
    ("west", (-30, 0, 0), 90),
    ("east", (30, 0, 0), 270),
]

for n in range(LAYERS):
    top = -88 - 40 * n         # top face of this storey
    # interior: 2x2 core brick and two plates
    core = []
    add(core, f"L{n}-core", "3003.dat", WHITE, [0, top, 0], purpose="Core brick 2 x 2")
    add(core, f"L{n}-core-plate-a", "3022.dat", WHITE, [0, top + 24, 0], purpose="Core plate 2 x 2")
    add(core, f"L{n}-core-plate-b", "3022.dat", WHITE, [0, top + 32, 0], purpose="Core plate 2 x 2")
    steps.append(core)

    # corners: 1 x 1 brick plus two 1 x 1 plates, 40 LDU per storey
    corners = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = 30 * sx, 30 * sz
            cid = f"L{n}-corner-{'w' if sx<0 else 'e'}{'n' if sz<0 else 's'}"
            add(corners, cid, "3005.dat", WHITE, [x, top, z], purpose="Corner brick 1 x 1")
            add(corners, cid + "-p1", "3024.dat", WHITE, [x, top + 24, z], purpose="Corner plate 1 x 1")
            add(corners, cid + "-p2", "3024.dat", WHITE, [x, top + 32, z], purpose="Corner plate 1 x 1")
    steps.append(corners)

    # SNOT walls: studs outward. Colours: red band in storey 1, one clear window in storey 2.
    walls = []
    for name, (ox, _, oz), yaw in FACES:
        colour = WHITE
        if n == 1:
            colour = RED
        if n == 0 and name == "north":
            colour = BLACK  # door
        if n == 2 and name == "west":
            colour = GLASS  # window
        add(walls, f"L{n}-wall-{name}", "67329.dat", colour, [ox, top, oz], yaw=yaw,
            purpose="Brick 1 x 2 x 1.667 with 8 studs on 3 sides (SNOT wall)")
    steps.append(walls)

# ---- gallery deck over the wall tops ----
ytop = -88 - 40 * (LAYERS - 1)     # top face of the highest storey
deck_y = ytop - 8                  # plates sit above the storey
deck = []
add(deck, "deck-north", "3710.dat", DARK, [0, deck_y, -30], purpose="Plate 1 x 4 gallery edge")
add(deck, "deck-south", "3710.dat", DARK, [0, deck_y, 30], purpose="Plate 1 x 4 gallery edge")
add(deck, "deck-west", "3023b.dat", DARK, [-30, deck_y, 0], yaw=90, purpose="Plate 1 x 2 gallery edge")
add(deck, "deck-east", "3023b.dat", DARK, [30, deck_y, 0], yaw=90, purpose="Plate 1 x 2 gallery edge")
steps.append(deck)

# ---- lantern room and roof ----
lantern = []
add(lantern, "lantern-a", "3003.dat", GLASS, [0, ytop - 24, 0], purpose="Lantern glass 2 x 2 (lower)")
add(lantern, "lantern-b", "3003.dat", GLASS, [0, ytop - 48, 0], purpose="Lantern glass 2 x 2 (upper)")
steps.append(lantern)

roof = []
add(roof, "roof-cap", "3022.dat", DARK, [0, ytop - 56, 0], purpose="Roof plate 2 x 2")
add(roof, "beacon-base", "3022.dat", YELLOW, [0, ytop - 64, 0], purpose="Beacon 2 x 2 plate, aligned on the roof cap studs")
steps.append(roof)

plan = {
    "version": 1,
    "author": "Claude (LDraw Nova agent)",
    "sections": [
        {
            "name": "lighthouse.ldr",
            "description": "Sideways-stud lighthouse: SNOT wall tower on a plinth, glazed lantern",
            "steps": steps,
        }
    ],
}

OUT.write_text(json.dumps(plan, indent=2) + "\n")
print("wrote", OUT, "steps", len(steps), "placements",
      sum(len(s) for s in steps))
