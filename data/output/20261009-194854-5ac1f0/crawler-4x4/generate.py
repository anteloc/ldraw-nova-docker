"""crawler-4x4 v5b — fix engine pin collision: single central block avoiding end pins.

End pin_holes 0/6 (X=+-60) have pins protruding; bricks covering them collide.
Use one central 2x4 (stud 2, X=-30..+30) + one stacked on top.
"""
from ldraw_tools.kit import Model

m = Model("crawler-4x4", "Inferno 4x4 Rock Crawler Buggy — V6, steering, ladder chassis", family="car")

left = m.add("32278", "Black", at=(-60, -70, 0), axes={"y": "Y", "z": "Z"}, id="chassis-left")
crosses = []
for k in (0, 14):
    pin = m.mate("2780", "Black", "pin[0]", to=left.port(f"pin_hole[{k}]"), id=f"chassis-pin-left-{k}")
    crosses.append(
        m.mate("32524", "Black", "pin_hole[0]", to=pin.port("pin[2]"), along="X", id=f"chassis-cross-{k}")
    )
pin0 = m.mate("2780", "Black", "pin[0]", to=crosses[0].port("pin_hole[6]"), id="chassis-pin-right-0")
right = m.mate("32278", "Black", "pin_hole[0]", to=pin0.port("pin[2]"), along="Z", id="chassis-right")
m.pin("Black", between=(right.port("pin_hole[14]"), crosses[1].port("pin_hole[6]")), id="chassis-pin-right-14")

def axle_plate(hole, prefix):
    pl = m.mate("2780", "Black", "pin[0]", to=left.port(f"pin_hole[{hole}]"), id=f"{prefix}-pin-left")
    plate = m.mate("3738", "Black", "pin_hole[0]", to=pl.port("pin[2]"), along="-Z", id=f"{prefix}-plate")
    m.pin("Black", between=(right.port(f"pin_hole[{hole}]"), plate.port("pin_hole[6]")), id=f"{prefix}-pin-right")
    return plate

plate_front = axle_plate(2, "front-axle")
plate_rear = axle_plate(12, "rear-axle")
plate_mid = axle_plate(7, "mid")
plate_engine = axle_plate(10, "engine")

fb_left = m.place("32000", "Black", on=plate_front.port("stud[2]"), cell=(0, 0), level=0, turn=90, id="front-brick-left")
fb_right = m.place("32000", "Black", on=plate_front.port("stud[5]"), cell=(0, 0), level=0, turn=90, id="front-brick-right")
rb_left = m.place("32000", "Black", on=plate_rear.port("stud[2]"), cell=(0, 0), level=0, turn=90, id="rear-brick-left")
rb_right = m.place("32000", "Black", on=plate_rear.port("stud[5]"), cell=(0, 0), level=0, turn=90, id="rear-brick-right")

front_axle = m.mate("3708", "Black", "axle[0]", to=fb_left.port("pin_hole[0]"), slide=30, toward="X", id="front-axle")
m.mate("3739", "Black", "axle_hole[0]", to=front_axle.port("axle[0]"), slide=110, toward="X", id="front-wheel-right")
m.mate("3739", "Black", "axle_hole[0]", to=front_axle.port("axle[0]"), slide=110, toward="-X", id="front-wheel-left")

rear_axle = m.mate("3708", "Black", "axle[0]", to=rb_left.port("pin_hole[0]"), slide=30, toward="X", id="rear-axle")
m.mate("3739", "Black", "axle_hole[0]", to=rear_axle.port("axle[0]"), slide=110, toward="X", id="rear-wheel-right")
m.mate("3739", "Black", "axle_hole[0]", to=rear_axle.port("axle[0]"), slide=110, toward="-X", id="rear-wheel-left")

seat_left = m.place("4079", "White", on=plate_mid.port("stud[2]"), cell=(0, 0), level=0, turn=0, id="cockpit-seat-left")
seat_right = m.place("4079", "White", on=plate_mid.port("stud[4]"), cell=(0, 0), level=0, turn=0, id="cockpit-seat-right")

col_axle = m.mate("3705", "Black", "axle[0]", to=plate_mid.port("pin_hole[2]"), id="steering-column")
m.mate("2819", "Black", "axle_hole[0]", to=col_axle.port("axle[0]"), slide=20, toward="UP", id="steering-wheel")

# Engine: single central 2x4 + stacked 2x4 on top
eng_base = m.place("3001", "Bright_Light_Orange", on=plate_engine.port("stud[2]"), cell=(0, 0), level=0, turn=0, id="engine-block-base")
eng_top = m.place("3001", "Bright_Light_Orange", on=eng_base.port("stud[0]"), cell=(0, 0), level=0, turn=0, id="engine-block-top")

m.save("output/crawler-4x4/crawler-4x4.mpd")
