"""Ridgeback: a Technic 4x4 trail crawler.

Original composition built from tested kit recipes (technic-frame, gear-train,
small-car's mate() axle/rim/tyre chain, hinged-wing's hinge() technique,
engine-pod's side-stud bracket), combined toward a new subject. No official-set
source model is extracted or copied.

Palette: Dark_Bluish_Grey (structure), Lime (body), Black (tyres/trim),
Trans_Orange (accent lights/winch highlight).
"""
from ldraw_tools.kit import Model

STRUCT = "Dark_Bluish_Grey"
BODY = "Lime"
TRIM = "Black"
ACCENT = "Trans_Orange"

m = Model("ridgeback", "A Technic 4x4 trail crawler: portal-style suspension, "
          "a gear-driven winch and a hinged bonnet over a real piston engine",
          family="car")

# ---------------------------------------------------------------------------
# Chassis: a ladder frame of two Beam-15 rails (running along Z, front -Z),
# separated by exactly the Beam-7 cross member's own hole-to-hole span (120
# LDU, measured via `ports 32524`) so the cross members fit without stretch.
# Both rails are placed explicitly at that measured separation; every cross
# member is pinned at the left rail, then closes the loop at the same hole
# index on the already-placed right rail (technic-frame.md's pattern).
# ---------------------------------------------------------------------------
RAIL_SEPARATION = 120  # LDU: exactly beam7's pin_hole[0]-to-pin_hole[6] span
left_rail = m.add("32278", STRUCT, at=(-RAIL_SEPARATION / 2, 0, 0),
                   axes={"y": "Y", "z": "Z"}, id="chassis-left-rail")
right_rail = m.add("32278", STRUCT, at=(RAIL_SEPARATION / 2, 0, 0),
                    axes={"y": "Y", "z": "Z"}, id="chassis-right-rail")

CROSS_HOLES = {
    "front-bumper": 1,   # z=-120: winch / front bumper subframe mount
    "front-axle": 4,     # z=-60: front suspension mount
    "centre": 7,         # z=0: engine bay firewall / seat mount
    "rear-axle": 10,     # z=60: rear suspension mount
    "rear-bumper": 13,   # z=120: bed / rear bumper mount
}

crosses = {}
for name, k in CROSS_HOLES.items():
    pin_l = m.mate("2780", "Black", "pin[0]", to=left_rail.port(f"pin_hole[{k}]"),
                   id=f"pin-left-{name}")
    cross = m.mate("32524", STRUCT, "pin_hole[0]", to=pin_l.port("pin[2]"), along="X",
                    id=f"cross-{name}")
    crosses[name] = cross
    m.pin("Black", between=(cross.port("pin_hole[6]"), right_rail.port(f"pin_hole[{k}]")),
          id=f"pin-close-{name}")

m.next_step()

# ---------------------------------------------------------------------------
# Wheel corner: a vertical axle standoff hangs from a free hole in the axle
# cross member; a 10197 hub (pin_hole + two perpendicular axle stubs) turns
# that vertical line into a horizontal one. The hub's stub is male, so a
# 6538a axle joiner (two female axle_hole sockets) bridges it to a second,
# outward-extending axle -- the wide wheel disc mounts on that axle's own
# length (gear-train.md's axle-through-hole pattern), far enough to clear
# the strut. A cross member's own pin_hole[1] is world X=-40 (left side),
# pin_hole[5] is X=+40 (right side): its hole index maps directly to world
# X since it was mated along="X" when the chassis was built.
# ---------------------------------------------------------------------------
def wheel_corner(cross, k, outward, corner_id):
    strut = m.mate("3706", "Black", "axle[0]", to=cross.port(f"pin_hole[{k}]"),
                    slide=60, toward="DOWN", id=f"strut-{corner_id}")
    hub = m.mate("10197", STRUCT, "pin_hole[0]", to=strut.port("axle[0]"),
                  slide=60, toward="DOWN", along="X", id=f"hub-{corner_id}")
    joiner = m.mate("6538a", STRUCT, "axle_hole[0]", to=hub.port("axle[1]"),
                     id=f"joiner-{corner_id}")
    axle_ext = m.mate("3706", "Black", "axle[0]", to=joiner.port("axle_hole[1]"),
                       slide=60, toward=outward, id=f"axle-{corner_id}")
    wheel = m.mate("22253c01", TRIM, "axle_hole[0]", to=axle_ext.port("axle[0]"),
                    slide=60, toward=outward, id=f"wheel-{corner_id}")
    return strut, hub, joiner, axle_ext, wheel


wheel_corner(crosses["front-axle"], 1, "-X", "fl")
wheel_corner(crosses["front-axle"], 5, "X", "fr")
wheel_corner(crosses["rear-axle"], 1, "-X", "rl")
wheel_corner(crosses["rear-axle"], 5, "X", "rr")

m.save("output/20261009-201226-106ff6/ridgeback/ridgeback.mpd")
