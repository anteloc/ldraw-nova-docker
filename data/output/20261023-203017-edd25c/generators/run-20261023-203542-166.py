import re
p='output/flower-set/generate.py'
t=open(p).read()
# leaves
a=t.index('def leaf('); b=t.index('def ring(')
t=t[:a]+'''def leaf(s, y, phi, tilt=45):
    """2423 leaf: stud at origin, blade runs to local -Z; tilt lifts the blade outward."""
    R = Ry(phi) @ Rx(-tilt)
    d = Ry(phi) @ np.array([0.0, 0.0, -1.0])
    s.add("2423.dat", DGREEN, (14 * d[0], y, 14 * d[2]), R)

'''+t[b:]
t=t.replace('leaf(s, leaf_y - 2, 90, 40)','leaf(s, leaf_y - 6, 0, 50)').replace('leaf(s, leaf_y - 2, 270, 40)','leaf(s, leaf_y - 6, 180, 35)')
# rose
a=t.index('# ---- Rose'); b=t.index('# ---- Tulip')
t=t[:a]+'''# ---- Rose
s = new("rose.ldr", "Red rose on a 12-long axle", 240, 130)
s.add("3941.dat", DGREEN, (0, -24, 0))      # calyx
s.step()
s.add("3941.dat", DRED, (0, -48, 0))
s.add("3941.dat", RED, (0, -72, 0))
s.step()
ring(s, "11477.dat", RED, 8, 22, -46, 0, 40)            # outer petals opening outward
ring(s, "11477.dat", DRED, 4, 14, -78, 45, -20)         # inner petals curling in
s.add("6141.dat", RED, (0, -80, 0))
secs["rose"] = s.out()

'''+t[b:]
# tulip tier2 lean in
t=t.replace('Rz(90 - (8 if tier else 0))','Rz(90 + (14 if tier else -6))')
# lavender
a=t.index('# ---- Lavender'); b=t.index('# ---- Sunflower')
t=t[:a]+'''# ---- Lavender
s = new("lavender.ldr", "Lavender spike on a 16-long axle", 320, 160)
s.add("3022.dat", DGREEN, (0, -8, 0))
s.step()
heights = {(-10, -10): 13, (10, -10): 10, (-10, 10): 11, (10, 10): 14}
for (x, z), h in heights.items():
    for i in range(h):
        s.add("6141.dat", PURPLE if (i + (x > 0)) % 2 else DPURPLE, (x, -16 - 8 * i, z))
    s.add("4589.dat", MLAV, (x, -16 - 8 * h - 24 + 4 if False else -16 - 8 * h - 20, z)) if False else None
    s.add("98138.dat", MLAV, (x, -16 - 8 * h, z))
    s.step()
secs["lavender"] = s.out()

'''+t[b:]
t=t.replace('PURPLE, DPURPLE, BROWN','MLAV, PURPLE, DPURPLE, BROWN').replace('MLAV, PURPLE, DPURPLE, BROWN, DBROWN, TAN, PINK = 22, 85, 70','MLAV, PURPLE, DPURPLE, BROWN, DBROWN, TAN, PINK = 31, 22, 85, 70')
t=t.replace('''    s.add("4589.dat", MLAV, (x, -16 - 8 * h - 24 + 4 if False else -16 - 8 * h - 20, z)) if False else None\n''','')
open(p,'w').write(t)
import subprocess
print(subprocess.run('.venv/bin/python output/flower-set/generate.py 2>&1|tail -15; ./ldraw-agent review output/flower-set/flower-set.plan.json --force --contacts none >/dev/null; echo $?',shell=True,capture_output=True,text=True).stdout)