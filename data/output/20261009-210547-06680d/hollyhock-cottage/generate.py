"""Hollyhock Cottage: a storybook cottage with a shuttered feature window,
a covered porch, a ridge-top chimney and a front garden.

Reused from the `small-house` recipe (docs/reference/small-house.md): the
wall-with-openings, stepped gable roof, gable-infill and ridge construction,
generalised here to an arbitrary width/depth. Everything else (feature window
+ shutters, chimney, porch, garden) is new.
"""
from ldraw_tools.kit import Model

m = Model(
    "hollyhock-cottage",
    "A storybook cottage: covered porch with a shuttered feature window, a "
    "ridge-top chimney, and a front garden",
    family="building",
)

# --- Ground -----------------------------------------------------------
ground = m.place("3811", "Bright_Green", cell=(0, 0), level=0, id="ground")
L = ground.top

# --- House footprint ----------------------------------------------------
W, D = 14, 8          # studs; (W - 2) must be a multiple of 4 for the roof algorithm
x0, z0 = 9, 16        # min corner of the house on the baseplate
assert (W - 2) % 4 == 0, "W-2 must be a multiple of 4 for the roof algorithm"

# --- Walls, with door + 3 window openings --------------------------------
m.wall("Tan", start=(x0, z0), length=W, courses=6, level=L, along="X", prefix="front",
       openings=[(1, 4, 1, 3), (7, 4, 0, 5)])           # feature window, then door
m.wall("Tan", start=(x0, z0 + D - 1), length=W, courses=6, level=L, along="X", prefix="back",
       openings=[(6, 2, 2, 3)])
m.wall("Tan", start=(x0, z0 + 1), length=D - 2, courses=6, level=L, along="Z", prefix="left",
       openings=[(2, 2, 2, 3)])
m.wall("Tan", start=(x0 + W - 1, z0 + 1), length=D - 2, courses=6, level=L, along="Z", prefix="right")

# --- Door -----------------------------------------------------------
frame = m.place("60596", "Reddish_Brown", cell=(x0 + 7, z0), level=L, id="door-frame")
m.mate("60623", "Reddish_Brown", "hinge[0]", to=frame.port("hinge[0]"), id="door")

# --- Front feature window with hinged shutters ---------------------------
window_front = m.place("3853", "Reddish_Brown", cell=(x0 + 1, z0), level=L + 3, id="window-front")
m.hinge("3856", "Sand_Green", "hinge[0]", to=window_front.port("hinge[0]"), angle=90, id="shutter-left")
m.hinge("3856", "Sand_Green", "hinge[0]", to=window_front.port("hinge[1]"), angle=-90, id="shutter-right")

# --- Back window and gable (side) window --------------------------------
m.place("60592", "Sand_Green", cell=(x0 + 6, z0 + D - 1), level=L + 6, id="window-back")
m.place("60592", "Sand_Green", cell=(x0, z0 + 3), level=L + 6, turn=90, id="window-left")

# --- Roof: stepped slopes, gable infill, ridge --------------------------
top = L + 18
n_four = (W - 2) // 4
for course in range(D // 2 - 1):
    z_front = z0 + course
    z_back = z0 + D - 2 - course
    lvl = top + 3 * course
    for i in range(n_four):
        x = x0 + 4 * i
        m.place("3037", "Reddish_Brown", cell=(x, z_front), level=lvl, id=f"roof-front-{course}-{i}")
        m.place("3037", "Reddish_Brown", cell=(x, z_back), level=lvl, turn=180, id=f"roof-back-{course}-{i}")
    xend = x0 + 4 * n_four
    m.place("3039", "Reddish_Brown", cell=(xend, z_front), level=lvl, id=f"roof-front-{course}-end")
    m.place("3039", "Reddish_Brown", cell=(xend, z_back), level=lvl, turn=180, id=f"roof-back-{course}-end")

for course in range(D // 2 - 2):
    for x in (x0, x0 + W - 1):
        length = D - 4 - 2 * course
        m.wall("Tan", start=(x, z0 + 2 + course), length=length, courses=1,
               level=top + 3 * course, along="Z", prefix=f"gable-{x}-{course}")

ridge_level = top + 3 * (D // 2 - 1)
ridge_z = z0 + D // 2 - 1
for i in range(n_four):
    x = x0 + 4 * i
    m.place("3041", "Reddish_Brown", cell=(x, ridge_z), level=ridge_level, id=f"ridge-{i}")
xend = x0 + 4 * n_four
ridge_end = m.place("3043", "Reddish_Brown", cell=(xend, ridge_z), level=ridge_level, id="ridge-end")

# --- Chimney, stacked on the ridge end -----------------------------------
# A plain place(level=ridge_end.top) left the chimney geometrically seated
# but not graph-connected to the sloped ridge piece, so mate the first brick
# onto the ridge-end's own stud_receptacle port explicitly.
chimney_cell = (xend, ridge_z)
chimney = m.mate("6143", "Dark_Bluish_Grey", "stud[0]", to=ridge_end.port("stud_receptacle[0]"), id="chimney-0")
for k in range(1, 4):
    chimney = m.place("6143", "Dark_Bluish_Grey", cell=chimney_cell, level=chimney.top, id=f"chimney-{k}")
cap = m.place("6141", "Dark_Bluish_Grey", cell=chimney_cell, level=chimney.top, id="chimney-cap")
m.place("6141", "Trans_Orange", cell=chimney_cell, level=cap.top, id="chimney-glow")

# --- Porch: posts, canopy, floor stones ----------------------------------
post_l = m.place("3005", "Reddish_Brown", cell=(x0 + 6, z0 - 3), level=L, id="porch-post-left-0")
for k in range(1, 4):
    post_l = m.place("3005", "Reddish_Brown", cell=(x0 + 6, z0 - 3), level=post_l.top, id=f"porch-post-left-{k}")
post_r = m.place("3005", "Reddish_Brown", cell=(x0 + 11, z0 - 3), level=L, id="porch-post-right-0")
for k in range(1, 4):
    post_r = m.place("3005", "Reddish_Brown", cell=(x0 + 11, z0 - 3), level=post_r.top, id=f"porch-post-right-{k}")

# Canopy: a single depth row resting on both posts (kept to one row so a
# single bridge closes every seam, with no row-to-row seam left open).
m.fill("Reddish_Brown", cell=(x0 + 6, z0 - 3), size=(6, 1), level=post_l.top, part="plate")
m.place("3710", "Reddish_Brown", cell=(x0 + 7, z0 - 3), level=post_l.top + 1, id="canopy-bridge")

m.place("4150", "Dark_Bluish_Grey", cell=(x0 + 8, z0 - 2), level=L, id="porch-stone-0")
m.place("4150", "Dark_Bluish_Grey", cell=(x0 + 8, z0 - 5), level=L, id="path-stone-1")
m.place("4150", "Dark_Bluish_Grey", cell=(x0 + 8, z0 - 8), level=L, id="path-stone-2")
m.place("4150", "Dark_Bluish_Grey", cell=(x0 + 8, z0 - 11), level=L, id="path-stone-3")

# --- Garden: tree, flowers, fence ----------------------------------------
m.place("3470", "Dark_Green", cell=(x0 - 6, z0 - 8), level=L, id="tree")

flower_spots = [
    (x0 - 5, z0 - 3, "4727", "Magenta"),
    (x0 - 3, z0 - 2, "3742", "Yellow"),
    (x0 - 5, z0 - 1, "3742", "Magenta"),
    (x0 + 17, z0 + 2, "4727", "Yellow"),
    (x0 + 19, z0 + 1, "3742", "Magenta"),
    (x0 + 18, z0 - 1, "3742", "Yellow"),
]
for i, (fx, fz, ref, colour) in enumerate(flower_spots):
    m.place(ref, colour, cell=(fx, fz), level=L, id=f"flower-{i}")

# Fence (33303 is 4 studs long): two segments end-to-end, 4 studs apart
for i, fz in enumerate(range(z0 + 1, z0 + 9, 4)):
    m.place("33303", "Sand_Green", cell=(x0 + 14, fz), level=L, turn=90, id=f"fence-{i}")

m.save("output/hollyhock-cottage/hollyhock-cottage.mpd")
