
import pathlib
p = pathlib.Path("/data/output/20261011-200214-c8293e/seaside-cabin/generate.py")
s = p.read_text()
rep = [
 ("GREEN = 2       # Planting", "GREEN = 2       # Planting\nWHITE = 15      # White: upper cladding, gable and ceiling trim\nDOOR = 4        # Red door"),
 ("def wall(steps_by_course, axis, fixed, start, length_studs, courses, openings, base):",
  "def wall(steps_by_course, axis, fixed, start, length_studs, courses, openings, base, colour=WOOD):"),
 ("fill_course(step, axis, fixed, start, length_studs, origin_y(c), WOOD, gaps, f\"{base}-c{c}\")",
  "fill_course(step, axis, fixed, start, length_studs, origin_y(c), colour, gaps, f\"{base}-c{c}\")"),
 ("(2, 4, {1, 2}, None),        # door", "(2, 4, {1, 2}, DOOR),        # red door panel"),
 ('wall(steps, "x", 80, -80, 8, upper_courses, upper_front, "uf")', 'wall(steps, "x", 80, -80, 8, upper_courses, upper_front, "uf", WHITE)'),
 ('wall(steps, "x", -80, -80, 8, upper_courses, upper_back, "ub")', 'wall(steps, "x", -80, -80, 8, upper_courses, upper_back, "ub", WHITE)'),
 ('wall(steps, "z", -60, -60, 6, upper_courses, upper_left, "ul")', 'wall(steps, "z", -60, -60, 6, upper_courses, upper_left, "ul", WHITE)'),
 ('wall(steps, "z", 60, -60, 6, upper_courses, upper_right, "ur")', 'wall(steps, "z", 60, -60, 6, upper_courses, upper_right, "ur", WHITE)'),
 ('add(gable, "3003.dat", WOOD,', 'add(gable, "3003.dat", WHITE,'),
 ('add(ceiling, "3001.dat", WOOD,', 'add(ceiling, "3001.dat", WHITE,'),
]
for a,b in rep:
    assert s.count(a) == 1, a
    s = s.replace(a,b)
p.write_text(s)
print("patched")
