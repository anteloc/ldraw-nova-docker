import sys
sys.path.insert(0, "/opt/ldraw-nova")
from ldraw_tools.kit import Model

m = Model("diag", "diagnostic")
RAIL_SEPARATION = 120
left_rail = m.add("32278", "Dark_Bluish_Grey", at=(-60, 0, 0), axes={"y": "Y", "z": "Z"}, id="left-rail")
right_rail = m.add("32278", "Dark_Bluish_Grey", at=(60, 0, 0), axes={"y": "Y", "z": "Z"}, id="right-rail")
pin_l = m.mate("2780", "Black", "pin[0]", to=left_rail.port("pin_hole[4]"), id="pin-l")
cross = m.mate("32524", "Dark_Bluish_Grey", "pin_hole[0]", to=pin_l.port("pin[2]"), along="X", id="cross")
m.pin("Black", between=(cross.port("pin_hole[6]"), right_rail.port("pin_hole[4]")), id="pin-close")

for k, label in ((1, "left k=1"), (5, "right k=5")):
    strut = m.mate("3706", "Black", "axle[0]", to=cross.port(f"pin_hole[{k}]"), slide=60, toward="DOWN", id=f"strut-{k}")
    print(label, "strut axle[0] world axis:", strut.port("axle[0]").A, "pos:", strut.port("axle[0]").P)
    hub = m.mate("10197", "Dark_Bluish_Grey", "pin_hole[0]", to=strut.port("axle[0]"), slide=60, toward="DOWN", along="X", id=f"hub-{k}")
    print(label, "hub axle[1] world axis:", hub.port("axle[1]").A, "pos:", hub.port("axle[1]").P)
    joiner = m.mate("6538a", "Dark_Bluish_Grey", "axle_hole[0]", to=hub.port("axle[1]"), id=f"joiner-{k}")
    print(label, "joiner axle_hole[1] world axis:", joiner.port("axle_hole[1]").A, "pos:", joiner.port("axle_hole[1]").P)
    print(label, "joiner box:", joiner.box)
    print()
