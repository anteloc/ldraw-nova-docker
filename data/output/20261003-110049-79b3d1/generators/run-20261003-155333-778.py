
import pathlib
p = pathlib.Path("output/garden-cottage/generate.py")
s = p.read_text()
s = s.replace('("back", 2.5, 4, 1, 3, "window"),', '("back", 2, 4, 1, 3, "window"),')
p.write_text(s)
print("patched")
