
import pathlib, re
p = pathlib.Path("/data/output/20261011-200214-c8293e/seaside-cabin/generate.py")
s = p.read_text()
s = s.replace("for k, zc in enumerate((160, 180, 200, 220)):", "for k, zc in enumerate((160, 200, 240)):")
s = s.replace('add(garden, "3003.dat", PINK, -70, -24, 150, 0, "planter-l")', 'add(garden, "3003.dat", PINK, -70, -24, 170, 0, "planter-l")')
s = s.replace('add(garden, "3003.dat", PINK, 30, -24, 150, 0, "planter-r")', 'add(garden, "3003.dat", PINK, 30, -24, 170, 0, "planter-r")')
s = s.replace('add(garden, "3022.dat", GREEN, -70, -32, 150, 0, "plant-l")', 'add(garden, "3022.dat", GREEN, -70, -32, 170, 0, "plant-l")')
s = s.replace('add(garden, "3022.dat", GREEN, 30, -32, 150, 0, "plant-r")', 'add(garden, "3022.dat", GREEN, 30, -32, 170, 0, "plant-r")')
p.write_text(s)
print("ok")
