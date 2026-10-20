"""Saltline X-9: original open-geared Technic salt-flat streamliner.

Frame bays use the pinned-beam technic-frame recipe; the reduction pair follows
gear-train's measured shaft spacing. All dressing is original to this model.
"""
from ldraw_tools.kit import Model

m = Model("saltline-x9", "Salt-flat streamliner with exposed reduction and twin tails", family="car")

# Two 15-hole longitudinal stringers; vertical pins and braced cross pieces make
# a rigid ladder. The upper layer sandwiches the transverse axle bearings.
left = m.add("32278", "Dark_Bluish_Grey", at=(-60, -80, 0), axes={"y": "Y", "z": "Z"}, id="mid-frame-left")
right = m.add("32278", "Dark_Bluish_Grey", at=(60, -80, 0), axes={"y": "Y", "z": "Z"}, id="mid-frame-right")
crosses = {}
for name, n in (("front", 3), ("cockpit", 7), ("rear", 8)):
    pin = m.mate("2780", "Black", "pin[0]", to=left.port(f"pin_hole[{n}]"), id=f"{name}-frame-left-pin")
    cross = m.mate("32524", "Dark_Bluish_Grey", "pin_hole[0]", to=pin.port("pin[2]"), along="X", id=f"{name}-frame-cross")
    crosses[name] = cross
    m.pin("Black", between=(cross.port("pin_hole[6]"), right.port(f"pin_hole[{n}]")), id=f"{name}-frame-right-pin")


# Two vertical crossblocks beside each stringer support a transverse rear shaft;
# the right-side pair also carries the accessible 8:24 reduction stage.
bearings = {}
for label, rail, hole in (("front-left", left, 0), ("front-right", right, 0),
                          ("output-left", left, 14), ("output-right", right, 14),
                          ("input-right", right, 10)):
    pin = m.mate("2780", "Black", "pin[0]", to=rail.port(f"pin_hole[{hole}]"), id=f"{label}-bearing-pin")
    bearings[label] = m.mate("32184", "Dark_Bluish_Grey", "pin_hole[0]", to=pin.port("pin[2]"),
                              along="Z", id=f"{label}-bearing")
# Span the 6-stud bearing separation with a 12L axle, placing wheels outboard.
for station, z in (("front", -160), ("rear", 120)):
    shaft = m.mate("3708", "Black", "axle[0]", to=bearings[("front" if station == "front" else "output") + "-left"].port("axle_hole[0]"),
                   slide=60, toward="X", id=f"{station}-wheel-shaft")

    for side in ("left", "right"):
        m.mate("56904c01", "Black", "axle_hole[0]",
               to=shaft.port("axle[0]"), slide=100, toward="-X" if side == "left" else "X",
               id=f"{station}-wheel-{side}")

    if station == "rear":
        output_shaft = shaft

# The 8T input drives a 24T gear on the wheel shaft, four studs away.
gear = m.mate("3648b", "Dark_Bluish_Grey", "axle_hole[0]", to=output_shaft.port("axle[0]"),
              slide=30, toward="X", id="drive-output-24t")
input_shaft = m.mate("3705", "Black", "axle[0]", to=bearings["input-right"].port("axle_hole[1]"),
                     slide=40, toward="-X", id="drive-input-shaft")
small = m.mate("3647", "Dark_Bluish_Grey", "axle_hole[0]", to=input_shaft.port("axle[0]"),
               slide=10, toward="X", id="drive-input-8t")


# A second layer of short beams above the frame carries the side skins.
upper = {}
for side, rail in (("left", left), ("right", right)):
    pin = m.mate("2780", "Black", "pin[0]", to=rail.port("pin_hole[11]"),
                 flip=True, id=f"upper-{side}-pin")
    upper[side] = m.mate("32525", "Black", "pin_hole[8]", to=pin.port("pin[2]"),
                         along="Z", id=f"upper-{side}-rail")

for side, rail in (("left", left), ("right", right)):
    top = upper[side]
    for bottom_hole, top_hole in ((5, 2), (6, 3)):
        m.pin("Black", between=(rail.port(f"pin_hole[{bottom_hole}]"),
                                 top.port(f"pin_hole[{top_hole}]")),
              id=f"upper-{side}-lock-{bottom_hole}")

# A pinned central spear stretches forward from the front frame crossmember.
nose_pin = m.mate("2780", "Black", "pin[0]", to=crosses["front"].port("pin_hole[3]"),
                  id="nose-keel-pin")
nose = m.mate("32525", "Orange", "pin_hole[8]", to=nose_pin.port("pin[2]"),
              along="Z", id="nose-keel")
# Narrow ahead of the axle, the nose becomes broader beside the cockpit.

# Side fairings attach directly to the upper rails with friction pins.
for side, rail, fairing in (("left", upper["left"], "64681"), ("right", upper["right"], "64393")):
    pin = m.mate("2780", "Black", "pin[0]", to=rail.port("pin_hole[1]"),
                 flip=True, id=f"body-{side}-fairing-pin")
    shell = m.mate(fairing, "White", "pin_hole[5]", to=pin.port("pin[2]"),
                   along="Z", id=f"body-{side}-fairing")


# An extension crossbeam supports a narrow, sculpted forward fairing.
nose_bridge = m.mate("2780", "Black", "pin[0]", to=nose.port("pin_hole[1]"),
                      id="nose-front-join")
nose_cross = m.mate("32316", "Dark_Bluish_Grey", "pin_hole[2]", to=nose_bridge.port("pin[2]"),
                    along="X", id="nose-front-cross")
for side, hole in (("left", 0), ("right", 4)):
    fastener = m.mate("2780", "Black", "pin[0]", to=nose_cross.port(f"pin_hole[{hole}]"),
                      flip=True, id=f"nose-{side}-beam-pin")
    beam = m.mate("32524", "White", "pin_hole[3]", to=fastener.port("pin[2]"),
                  along="Z", id=f"nose-{side}-shoulder")
    curve_pin = m.mate("2780", "Black", "pin[0]", to=beam.port("pin_hole[1]"),
                       id=f"nose-{side}-curve-pin")

    curve = m.mate("87080" if side == "left" else "87086", "White", "pin_hole[6]",
                   to=curve_pin.port("pin[2]"), along="Z", id=f"nose-{side}-curve")


# A raised instrument shelf and nose spine leave the reduction visible aft.
cockpit_pin = m.mate("2780", "Black", "pin[0]", to=nose.port("pin_hole[9]"),
                     flip=True, id="cockpit-mount-pin")

cockpit_shelf = m.mate("32316", "Dark_Bluish_Grey", "pin_hole[2]", to=cockpit_pin.port("pin[2]"),
                       along="X", id="cockpit-shelf")
seat_pin = m.mate("2780", "Black", "pin[0]", to=cockpit_shelf.port("pin_hole[2]"),
                   flip=True, id="cockpit-seat-pin")

seat_spine = m.mate("32316", "Black", "pin_hole[1]", to=seat_pin.port("pin[2]"),
                    along="Z", id="cockpit-seat-spine")
# Driver seat, fitted sideways to a pin between the cockpit shell and spine.
seat_fastener = m.mate("2780", "Black", "pin[0]", to=seat_spine.port("pin_hole[2]"),
                       flip=True, id="cockpit-seat-fastener")
seat = m.mate("2717", "Black", "pin_hole[0]", to=seat_fastener.port("pin[2]"),
              along="Z", id="cockpit-driver-seat")

# Paired tail stabilizers: pin mounts at the rear of the upper frame.
for side, rail in upper.items():
    pin = m.mate("2780", "Black", "pin[0]", to=rail.port("pin_hole[10]"),
                 id=f"tail-{side}-root-pin")
    mount = m.mate("32523", "White", "pin_hole[0]", to=pin.port("pin[2]"),
                   along="Z", id=f"tail-{side}-pedestal")
    fin_pin = m.mate("2780", "Black", "pin[0]", to=mount.port("pin_hole[1]"),
                     flip=True, id=f"tail-{side}-fin-pin")
    fin = m.mate("32524", "White", "pin_hole[0]", to=fin_pin.port("pin[2]"),
                 along="Z", id=f"tail-{side}-fin")
    cap_pin = m.mate("2780", "Black", "pin[0]", to=fin.port("pin_hole[4]"),
                     flip=True, id=f"tail-{side}-cap-pin")
    cap = m.mate("87080" if side == "left" else "87086", "Orange", "pin_hole[5]",
                 to=cap_pin.port("pin[2]"), along="Z", id=f"tail-{side}-cap")


# The input axle projects alongside the exposed 8T gear for a hand dial.
knob = m.mate("3713", "Orange", "axle_hole[0]", to=input_shaft.port("axle[0]"),
              slide=30, toward="-X", id="drive-control-knob")

# Driver's bright instrument ring nests on the supported cockpit shelf.

# The forward underside has a deep orange splitter under the white intakes.
split_pin = m.mate("2780", "Black", "pin[0]", to=nose.port("pin_hole[0]"),
                   flip=True, id="nose-splitter-pin")
splitter = m.mate("32523", "Orange", "pin_hole[1]", to=split_pin.port("pin[2]"),
                  along="Z", id="nose-splitter")


# The existing white fairing pair leaves an orange central racing stripe open.

# Raised tail, open engine bay, and forked nose leave the Technic frame visible.

# Black wheels and orange fork tips identify the machine from a thumbnail.

# A low central cowl seats in the existing studs above the orange keel.
hood = m.place("3034", "White", cell=(-1, -10), level=12.5, turn=90, id="nose-cowl")


m.save("output/saltline-x9/saltline-x9.mpd")
