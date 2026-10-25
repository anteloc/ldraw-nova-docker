"""Meadow Posy Set generator. Run: .venv/bin/python output/flower-set/generate.py"""
import math, json
from pathlib import Path
import numpy as np
from ldraw_tools.common import atomic_write, dumps, get_parts
from ldraw_tools.workflow import build_checked

def Ry(d):
    t = math.radians(d); c, s = math.cos(t), math.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def Rz(d):
    t = math.radians(d); c, s = math.cos(t), math.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def Rx(d):
    t = math.radians(d); c, s = math.cos(t), math.sin(t)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
I3 = np.eye(3)
def M(m):
    return [[round(float(x), 9) + 0.0 for x in r] for r in m]
AXLE_V = [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]  # axle along +/-Y (as in the 10280 stems)

SAND, DGREEN, GREEN, WHITE, YELLOW, RED, DRED, ORANGE, DORANGE = 378, 288, 2, 15, 14, 4, 320, 25, 484
MLAV, PURPLE, DPURPLE, BROWN, DBROWN, TAN, PINK = 31, 22, 85, 70, 308, 19, 5

class Sec:
    def __init__(self, name, desc):
        self.name, self.desc, self.steps, self.cur, self.n = name, desc, [], [], 0
    def add(self, ref, colour, at, m=None):
        self.n += 1
        p = {"id": f"p{self.n}", "ref": ref, "colour": colour, "at": [round(float(v), 3) for v in at]}
        if m is not None and not np.allclose(m, I3):
            p["matrix"] = M(m)
        self.cur.append(p)
    def step(self):
        if self.cur: self.steps.append(self.cur); self.cur = []
    def out(self):
        self.step()
        return {"name": self.name, "description": self.desc, "steps": self.steps}

def leaf(s, y, phi, tilt=45):
    """2423 leaf: stud at origin, blade runs to local -Z; tilt lifts the blade outward."""
    R = Ry(phi) @ Rx(-tilt)
    d = Ry(phi) @ np.array([0.0, 0.0, -1.0])
    s.add("2423.dat", DGREEN, (14 * d[0], y, 14 * d[2]), R)

def ring(s, ref, colour, n, r, y, off=0, tilt=0):
    for k in range(n):
        th = off + 360.0 * k / n
        c, sn = math.cos(math.radians(th)), math.sin(math.radians(th))
        R = Ry(th) @ Rz(-tilt)    # local x = radial; positive tilt lifts the outer end
        s.add(ref, colour, (r * c, y, -r * sn), R)

secs = {}
def new(name, desc, L, leaf_y):
    s = Sec(name, desc)
    s.add({160: "3707", 180: "60485", 240: "3708", 320: "50451"}[L] + ".dat", SAND, (0, L / 2, 0), np.array(AXLE_V))
    s.add("4032a.dat", GREEN, (0, 0, 0))
    s.step()
    # collar and leaves on the stem
    s.add("4032a.dat", DGREEN, (0, leaf_y, 0))
    leaf(s, leaf_y - 6, 0, 50)
    leaf(s, leaf_y - 6, 180, 35)
    s.step()
    return s

# ---- Daisy
s = new("daisy.ldr", "White daisy on a 9-long axle", 180, 100)
ring(s, "35480.dat", WHITE, 6, 26, -8, 0)
ring(s, "35480.dat", WHITE, 6, 26, -16, 30)
s.step()
s.add("14769.dat", YELLOW, (0, -24, 0))
s.add("6141.dat", DORANGE, (0, -28, 0))   # tiny stud centre
secs["daisy"] = s.out()

# ---- Rose
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

# ---- Tulip
s = new("tulip.ldr", "Orange tulip on an 8-long axle", 160, 90)
s.add("3941.dat", DGREEN, (0, -24, 0))
s.step()
s.add("3941.dat", YELLOW, (0, -48, 0))
s.step()
for tier, (y, col) in enumerate([(-14, DORANGE), (-30, ORANGE)]):
    for k in range(4):
        th = 90 * k
        c, sn = math.cos(math.radians(th)), math.sin(math.radians(th))
        R = Ry(th) @ Rz(90 + (14 if tier else -6))
        s.add("15068.dat", col, (20 * c, y - 20, -20 * sn), R)
s.step()
secs["tulip"] = s.out()

# ---- Lavender
s = new("lavender.ldr", "Lavender spike on a 16-long axle", 320, 160)
s.add("3022.dat", DGREEN, (0, -8, 0))
s.step()
heights = {(-10, -10): 8, (10, -10): 6, (-10, 10): 7, (10, 10): 9}
for (x, z), h in heights.items():
    for i in range(h):
        s.add("6141.dat", PURPLE if (i + (x > 0)) % 2 else DPURPLE, (x, -16 - 8 * i, z))
    s.add("98138.dat", MLAV, (x, -16 - 8 * h, z))
    s.step()
secs["lavender"] = s.out()

# ---- Sunflower
s = new("sunflower.ldr", "Sunflower on a 12-long axle", 240, 130)
s.add("3941.dat", DGREEN, (0, -24, 0))
s.step()
ring(s, "35480.dat", YELLOW, 8, 30, -32, 0)
ring(s, "35480.dat", ORANGE, 8, 30, -40, 22.5)
s.step()
s.add("3941.dat", DBROWN, (0, -48, 0))
s.add("14769.dat", BROWN, (0, -56 + 0, 0))
secs["sunflower"] = s.out()

# ---- main
LEN = {"tulip": 160, "daisy": 180, "lavender": 320, "rose": 240, "sunflower": 240}
POS = {"tulip": (-120, 20), "daisy": (-60, -20), "lavender": (0, 20), "rose": (60, -20), "sunflower": (120, 20)}
main = Sec("meadow-posy-main.ldr", "Meadow Posy Set: five flowers on a planter slab")
main.add("3027.dat", TAN, (0, 0, 0))
main.step()
for n, (x, z) in POS.items():
    main.add("3941.dat", BROWN, (x, -24, z))
main.step()
for n, (x, z) in POS.items():
    main.add(f"{n}.ldr", 16, (x, -12 - LEN[n], z))
main.step()

plan = {"version": 1, "author": "LDraw Nova agent (inspired by LEGO 10280 by Orion Pobursky)",
        "sections": [main.out()] + [secs[k] for k in POS]}
out = Path("output/flower-set")
atomic_write(out / "flower-set.plan.json", dumps(plan) + "\n")
text, _, report = build_checked(plan, get_parts(), detail="summary")
print("checks_passed", report.get("checks_passed"))
if not report.get("checks_passed"):
    print(dumps(report)[:4000])
else:
    atomic_write(out / "flower-set.mpd", text)
