
import pathlib
p = pathlib.Path("output/garden-cottage/generate.py")
s = p.read_text()
s = s.replace('''def gate3(c=RDBR):
    m = Module("gate3", "Three-stud garden gate matching the fence; underside Y=0")
    for x in (-1.5, 1.5):
        m.add("3005", c, x, 24, .5)
        m.add("3005", c, x, 48, .5)
    line(m, -1.5, .5, 3, 32, c, plate=True)
    line(m, -1.5, .5, 3, 56, c, plate=True)
    return m


''', '')
p.write_text(s)
print("gate3 removed")
