
import pathlib
p = pathlib.Path("/data/output/20261011-200214-c8293e/seaside-cabin/generate.py")
s = p.read_text()
s = s.replace("seg_start = start * 0 + (start + pos) * stud  # LDU of segment start (wall-local)",
              "seg_start = start + pos * stud  # LDU: start is the wall's first edge in LDU")
s = s.replace("centre = (start + (a + b) / 2) * stud", "centre = start + (a + b) / 2 * stud")
s = s.replace('add(garden, "3022.dat", GREEN, -70, -48, 150, 0, "plant-l")',
              'add(garden, "3022.dat", GREEN, -70, -32, 150, 0, "plant-l")')
s = s.replace('add(garden, "3022.dat", GREEN, 30, -48, 150, 0, "plant-r")',
              'add(garden, "3022.dat", GREEN, 30, -32, 150, 0, "plant-r")')
s = s.replace("# Roof: 45-degree slopes",
"""# Attic ceiling: three 2x4 bricks across the interior, resting on the upper wall tops
ceiling = []
for zc in (-40, 0, 40):
    add(ceiling, "3001.dat", WOOD, 0, origin_y(7), zc, 0, "ceiling")
steps["ceiling"] = ceiling

# Roof: 45-degree slopes""")
s = s.replace('steps["gable"] = gable\n', 'steps["gable"] = gable + steps.get("gable", [])\n')
# clean assembly: remove the first, superseded assembly block
start = s.index("# Assemble steps in build order")
end = s.index("# Courses are stored by number")
s = s[:start] + "# Assemble steps in build order\nglass_keys = [k for k in steps if isinstance(k, tuple) and k[0] == 'glass']\n" + s[end:]
s = s.replace('plan_steps.append(steps["gable"])\nplan_steps.append(steps["roof"])',
              'plan_steps.append(steps["gable"])\nplan_steps.append(steps["ceiling"])\nplan_steps.append(steps["roof"])')
p.write_text(s)
import subprocess
print(subprocess.run(["/data/../bin/true"]) if False else "patched")
print(s.count("ceiling"), "ceiling refs")
