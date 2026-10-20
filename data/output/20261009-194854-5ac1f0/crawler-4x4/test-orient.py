"""crawler-4x4 v1c — try along=-Z for plates (flip 180 from v1b)."""
from ldraw_tools.kit import Model

m = Model("crawler-4x4", "Inferno 4x4 Rock Crawler Buggy — V6, steering, ladder chassis", family="car")

left = m.add("32278", "Black", at=(-60, -70, 0), axes={"y": "Y", "z": "Z"}, id="chassis-left")
crosses = []
for k in (0, 14):
    pin = m.mate("2780", "Black", "pin[0]", to=left.port(f"pin_hole[{k}]"), id=f"chassis-pin-left-{k}")
    crosses.append(
        m.mate("32524", "Black", "pin_hole[0]", to=pin.port("pin[2]"), along="X", id=f"chassis-cross-{k}")
    )
pin = m.mate("2780", "Black", "pin[0]", to=pin.port("pin[2]"), along="Z", id="chassis-right") if False else None
# rebuild right correctly (keep v0 working lines)
# NOTE: redo right rail properly:
m2 = None
