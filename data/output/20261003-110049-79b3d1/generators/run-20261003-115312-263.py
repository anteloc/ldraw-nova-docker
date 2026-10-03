
import pathlib
p = pathlib.Path("output/garden-cottage/generate.py")
s = p.read_text()
s = s.replace(
"""    m.add(fence(10, RDBR), RDBR, -14, 0, 17, yaw=90, purpose="left fence")
    m.add(fence(10, RDBR), RDBR, 14, 0, 17, yaw=90, purpose="right fence")""",
"""    m.add(fence(9, RDBR), RDBR, -14, 0, 17.5, yaw=90,
          purpose="left fence between front and back rails")
    m.add(fence(9, RDBR), RDBR, 14, 0, 17.5, yaw=90,
          purpose="right fence between front and back rails")""")
p.write_text(s)
print("patched")
