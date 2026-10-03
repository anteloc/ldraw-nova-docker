
import pathlib
p = pathlib.Path("output/garden-cottage/generate.py")
s = p.read_text()

# A. Chimney sits ON the ridge tiles: module base at world y=-472 (ridge tile top).
s = s.replace('m.add(chimney(), DTAN, 5, -464, -7, id="ridge-chimney",',
              'm.add(chimney(), DTAN, 5, 472, -7, id="ridge-chimney",')

# B. Hall back wall: two window columns on each floor.
s = s.replace('back_rows = [(1, [-5]), (7, [-5])]',
              'back_rows = [(1, [-5, 3]), (7, [-5, 3])]')

# C. Wing back: window beside the door.
s = s.replace("""    openings = [
        ("back", -2, 4, 0, 5, "door"),
        ("left", 1, 4, 1, 3, "window"),
        ("right", 1, 4, 1, 3, "window"),
    ]""",
"""    openings = [
        ("back", -2, 4, 0, 5, "door"),
        ("back", 2.5, 4, 1, 3, "window"),
        ("left", 1, 4, 1, 3, "window"),
        ("right", 1, 4, 1, 3, "window"),
    ]""")

s = s.replace("""    for centre, width, r0, _, kind in by_side["back"]:
        m.add(door4(WHITE, RDBR), WHITE, centre, 8 + 24*r0, d/2 - .5, yaw=180)""",
"""    for centre, width, r0, _, kind in by_side["back"]:
        if kind == "door":
            m.add(door4(WHITE, RDBR), WHITE, centre, 8 + 24*r0, d/2 - .5, yaw=180)
        else:
            m.add(window4(WHITE, GLASS), WHITE, centre, 8 + 24*r0, d/2 - .5, yaw=180)""")

p.write_text(s)
print("patched")
