
import pathlib
p = pathlib.Path("output/garden-cottage/generate.py")
s = p.read_text()

# --- 1. Bed bases: 3034 plates -> 3068b tile slabs; tilled tiles h 12 -> 16
s = s.replace("""    # Bed bases (dark tan 2x8 plates, long axis in Z) + tilled tile surface.
    for x0, _ in BEDS:
        for dx in (1, 3):
            m.add("3034", DTAN, x0 + dx, 8, 17, yaw=90,
                  purpose="soil bed base plate")
        for x in range(x0, x0 + 4):
            for z in range(FZ0, FZ0 + FZD):
                m.add("3070b", DTAN, x + .5, 12, z + .5,
                      purpose="tilled soil tile")""",
"""    # Bed bases: dark tan 2x2 tile slabs (tile-on-tile, no stud clash);
    # tilled 1x1 tile surface one plate higher, z cells 14..19.
    for x0, _ in BEDS:
        for dx in (1, 3):
            for dz in (15, 19):
                m.add("3068b", DTAN, x0 + dx, 8, dz,
                      purpose="soil bed base tile")
        for x in range(x0, x0 + 4):
            for z in range(FZ0 + 1, FZ0 + FZD - 1):
                m.add("3070b", DTAN, x + .5, 16, z + .5,
                      purpose="tilled soil tile")""")

# --- 2. Crop heights: soil top now h=16 -> h = local_max + 16
s = s.replace('C("51270", ORANGE, x, 44, z, purpose="pumpkin")',
              'C("51270", ORANGE, x, 48, z, purpose="pumpkin")')
s = s.replace('C("37681", ORANGE, x, 44, z, purpose="root vegetable")',
              'C("37681", ORANGE, x, 48, z, purpose="root vegetable")')
s = s.replace('C("6255", BGRN, -7, 28, 17, purpose="cabbage")',
              'C("6255", BGRN, -7, 32, 17, purpose="cabbage")')
s = s.replace('C("6255", BGRN, -5, 28, 17, purpose="cabbage")',
              'C("6255", BGRN, -5, 32, 17, purpose="cabbage")')
s = s.replace('C("2423", DGRN, -1, 20, 14.5)', 'C("2423", DGRN, -1, 24, 14.5)')
s = s.replace('C("2423", DGRN, 0, 20, 14.5)', 'C("2423", DGRN, 0, 24, 14.5)')
s = s.replace('C("2423", BGRN, -1, 20, 18.5)', 'C("2423", BGRN, -1, 24, 18.5)')
s = s.replace('C("2423", BGRN, 0, 20, 18.5)', 'C("2423", BGRN, 0, 24, 18.5)')
s = s.replace('C("2417", BGRN, -0.5, 20, 16.5, purpose="leafy accent")',
              'C("2417", BGRN, -0.5, 24, 16.5, purpose="leafy accent")')
s = s.replace('C("4727", DPINK, 5, 36, 14.5)', 'C("4727", DPINK, 5, 40, 14.5)')
s = s.replace('C("4727", DPINK, 6, 36, 18.5)', 'C("4727", DPINK, 6, 40, 18.5)')
s = s.replace('C("3742", YELLOW, 5, 14, 17.5)', 'C("3742", YELLOW, 5, 18, 17.5)')
s = s.replace('C("3742", RED, 6, 14, 16)', 'C("3742", RED, 6, 18, 16)')
s = s.replace('C("3742", DPINK, 4.5, 14, 19.5)', 'C("3742", DPINK, 4.5, 18, 19.5)')
s = s.replace("""    for x, z in ((7, 13.5), (7, 17.5), (4.5, 20.5)):
        C("15279", GRN, x, 12, z)""",
"""    for x, z in ((7, 17.5), (4.5, 19.5)):
        C("15279", GRN, x, 16, z)""")
s = s.replace('C("2423", DGRN, 11, 20, 14.5)', 'C("2423", DGRN, 11, 24, 14.5)')
s = s.replace('C("2423", BGRN, 12, 20, 18.5)', 'C("2423", BGRN, 12, 24, 18.5)')
s = s.replace('C("2423", DGRN, 11, 20, 18.5)', 'C("2423", DGRN, 11, 24, 18.5)')
s = s.replace('C("7264", BGRN, 12, 23.2, 14.5, purpose="long-leaf plant")',
              'C("7264", BGRN, 12, 27.2, 14.5, purpose="long-leaf plant")')
s = s.replace('C("3742", YELLOW, 11, 14, 17)', 'C("3742", YELLOW, 11, 18, 17)')
s = s.replace('C("3742", RED, 12, 14, 16.5)', 'C("3742", RED, 12, 18, 16.5)')
s = s.replace("""    for x, z in ((10.5, 19.5), (13, 13.5)):
        C("15279", GRN, x, 12, z)""",
"""    for x, z in ((10.5, 19.5), (13, 19.5)):
        C("15279", GRN, x, 16, z)""")
# bed 1 edge flowers: move onto soil rows
s = s.replace('C("3742", YELLOW, -13.5, 14, 13.5)', 'C("3742", YELLOW, -12.5, 18, 14.5)')
s = s.replace('C("3742", RED, -11.5, 14, 20.5)', 'C("3742", RED, -11.5, 18, 19.5)')
s = s.replace('C("3742", YELLOW, -12.5, 14, 17.5)', 'C("3742", YELLOW, -13.5, 18, 17.5)')

# --- 3. Vine: clear the back fence
s = s.replace('C("16981", BGRN, 6, 56, 20.5, purpose="draping vine along trellis top")',
              'C("16981", BGRN, 6, 56, 19, purpose="draping vine along trellis top")')

# --- 4. Fence perimeter: clean corners, gate as a 3-stud opening
s = s.replace("""    # Fence perimeter with gate on the path.
    m.add(fence(26, RDBR), RDBR, -1, 0, 12, purpose="front fence to the gate")
    m.add(gate3(), RDBR, 12.5, 0, 12, purpose="gate on the garden path")
    m.add(fence(28, RDBR), RDBR, 0, 0, 22, purpose="back fence")
    m.add(fence(10, RDBR), RDBR, -14, 0, 17, yaw=90, purpose="left fence")
    m.add(fence(10, RDBR), RDBR, 14, 0, 17, yaw=90, purpose="right fence")""",
"""    # Fence perimeter; the 3-stud gap between the front fence post (X=11)
    # and the right fence post (X=14) is the gate opening at the path.
    m.add(fence(25, RDBR), RDBR, -1, 0, 12, purpose="front fence to the gate")
    m.add(fence(27, RDBR), RDBR, 0, 0, 22, purpose="back fence")
    m.add(fence(10, RDBR), RDBR, -14, 0, 17, yaw=90, purpose="left fence")
    m.add(fence(10, RDBR), RDBR, 14, 0, 17, yaw=90, purpose="right fence")""")

# --- 5. Paths: clear the steps and the bed edge
s = s.replace("""    # Paths: front to the steps, east connector, garden path through the gate.
    paved_path(m, -2, -24, 4, 6)
    paved_path(m, -2, -20, 16, 2)
    paved_path(m, 12, -18, 2, 32)""",
"""    # Paths: front to the steps, east connector (clearing the step cells
    # X=0..3), garden path through the gate opening (stops before the beds).
    paved_path(m, -2, -24, 4, 5)
    paved_path(m, -2, -20, 2, 2)
    paved_path(m, 4, -20, 10, 2)
    paved_path(m, 12, -18, 2, 30)""")

# --- 6. Planters: keep the left one, drop the colliding right one
s = s.replace("""    m.add(planter(DPINK), DPINK, -4, 0, -15, purpose="flanks the steps")
    m.add(planter(DPINK), DPINK, 8, 0, -15, purpose="flanks the steps")""",
"""    m.add(planter(DPINK), DPINK, -4, 0, -15, purpose="flanks the steps")""")

p.write_text(s)
print("patched")
