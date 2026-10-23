"""Generate output/city-park/park.plan.json (scenery + 20 minifigs via the minifig rig)."""
import json, math, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

OUT = "output/city-park"
FIGDIR = OUT + "/figs"
os.makedirs(FIGDIR, exist_ok=True)

P = []          # placements for main section
_n = {}


def uid(ref):
    k = ref.split(".")[0]
    _n[k] = _n.get(k, 0) + 1
    return f"{k}-{_n[k]}"


def norm(a):
    a = ((a + 180) % 360) - 180
    return a


def add(ref, col, x, y, z, yaw=0, matrix=None, purpose=None):
    p = {"id": uid(ref), "ref": ref, "colour": col,
         "at": [round(x, 3), round(y, 3), round(z, 3)]}
    if matrix is not None:
        p["matrix"] = matrix
    elif norm(yaw) != 0:
        p["yaw"] = norm(yaw)
    if purpose:
        p["purpose"] = purpose
    P.append(p)


class T:
    """Local frame: origin at a grid vertex, local front = -z, rotated by yaw (about +Y)."""

    def __init__(s, ox, oz, yaw=0, S=0):
        s.ox, s.oz, s.yaw, s.S = ox, oz, yaw, S

    def xz(s, lx, lz):
        r = math.radians(s.yaw)
        c, sn = round(math.cos(r)), round(math.sin(r))
        return s.ox + lx * c + lz * sn, s.oz - lx * sn + lz * c

    def put(s, ref, col, u, v, w, d, base, bh, ly=0):
        """footprint cells u..u+w-1, v..v+d-1 (after local rotation); base = height of support
        above S; bh = body height of part (8 plate, 24 brick)."""
        x, z = s.xz((u + w / 2) * 20, (v + d / 2) * 20)
        add(ref, col, x, s.S - base - bh, z, s.yaw + ly)

    def world(s, lx, lz):
        return s.xz(lx, lz)


G = T(0, 0)   # world: cell (u,v) -> x=u*20


# ---------------------------------------------------------------- ground
for bx in (-320, 0, 320):
    for bz in (-320, 0, 320):
        add("3867.dat", 2, bx, 0, bz)

# lawn stripes (bright green) for a mown look
for (u, v, w, d, ly) in [(-23, 5, 6, 4, 0), (-23, 9, 6, 4, 0), (3, 3, 4, 6, 90), (8, 18, 6, 4, 0),
                         (-12, 18, 6, 4, 0), (8, -22, 6, 4, 0)]:
    pass  # reserved (kept simple)

# plaza + paths (tan plates, surface -8)
for x0 in (-6, 0):
    for z0 in (-6, -2, 2):
        G.put("3032.dat", 19, x0, z0, 6, 4, 0, 8)
for x0 in (-24, -18, -12, 6, 12, 18):
    G.put("3032.dat", 19, x0, -2, 6, 4, 0, 8)
for z0 in (-24, -18, -12, 6, 12, 18):
    G.put("3032.dat", 19, -2, z0, 4, 6, 0, 8, 90)

# ---------------------------------------------------------------- pond + fountain
for layer in (8, 16):
    G.put("3460.dat", 71, -4, -4, 8, 1, layer, 8)
    G.put("3460.dat", 71, -4, 3, 8, 1, layer, 8)
    G.put("3666.dat", 71, -4, -3, 1, 6, layer, 8, 90)
    G.put("3666.dat", 71, 3, -3, 1, 6, layer, 8, 90)
G.put("3032.dat", 73, -3, -3, 6, 4, 8, 8)
G.put("3795.dat", 73, -3, 1, 6, 2, 8, 8)
fx, fz = 10, 10
add("3062b.dat", 15, fx, -16 - 24, fz)
add("3062b.dat", 15, fx, -16 - 48, fz)
add("4589.dat", 43, fx, -16 - 72, fz)
for (dx, dz) in ((-20, 0), (20, 0), (0, -20), (0, 20)):
    add("6141.dat", 43, fx + dx, -24, fz + dz)
for (u, v) in ((-3, -3), (2, -3), (-3, 2), (2, 2)):   # water-lily / pebbles
    add("6141.dat", 15 if (u + v) % 2 else 14, u * 20 + 10, -24, v * 20 + 10)


# ---------------------------------------------------------------- trees, lamps, flowers
def tree(u, v, leaf):
    x, z = u * 20 + 10, v * 20 + 10
    for i in range(5):
        add("3062b.dat", 6, x, -24 * (i + 1), z)
    for k in range(4):
        add("2417.dat", leaf if k % 2 == 0 else (leaf if leaf in (13,) else 10), x, -128 - 8 * k, z, 90 * k)


for (u, v, c) in [(-20, -5, 2), (-20, 7, 10), (-6, -18, 2), (7, -12, 10), (5, 19, 2), (-9, 18, 10),
                  (19, -7, 13), (-14, 10, 2), (20, 4, 10), (3, -22, 2)]:
    tree(u, v, c)


def lamp(u, v):
    x, z = u * 20 + 10, v * 20 + 10
    for i in range(4):
        add("3062b.dat", 72, x, -8 - 24 * (i + 1) + 8, z)   # plaza side: sits on ground (0) -> adjust below
    return


for (u, v) in ((-7, -7), (6, -7), (-7, 6), (6, 6)):
    x, z = u * 20 + 10, v * 20 + 10
    for i in range(4):
        add("3062b.dat", 72, x, -24 * (i + 1), z)
    add("3062b.dat", 46, x, -24 * 5, z)
    add("6141.dat", 72, x, -24 * 5 - 8, z)


def flowerbed(u, v, w=6, d=4, cols=(4, 14, 15, 13, 25)):
    G.put("3032.dat" if (w, d) == (6, 4) else "3031.dat", 6, u, v, w, d, 0, 8)
    i = 0
    for dv in range(d):
        for du in range(w):
            add("6141.dat", cols[(i * 2 + dv) % len(cols)], (u + du) * 20 + 10, -16, (v + dv) * 20 + 10)
            i += 1


flowerbed(-22, 14)
flowerbed(7, -9)
for u in (-22, -19):                                    # hedge behind the SW bed
    G.put("3010.dat", 2, u, 12, 4 if False else 3, 1, 0, 24) if False else None
G.put("3009.dat", 2, -22, 12, 6, 1, 0, 24)
G.put("3009.dat", 2, -22, 13, 6, 1, 0, 24)
G.put("3010.dat", 10, 3, -10, 4, 1, 0, 24) if False else None


# ---------------------------------------------------------------- benches
def bench(t, with_back=True):
    t.put("3005.dat", 72, -2, -3, 1, 1, 0, 24)
    t.put("3005.dat", 72, 1, -3, 1, 1, 0, 24)
    t.put("3005.dat", 72, -2, -1, 1, 1, 0, 24)
    t.put("3005.dat", 72, 1, -1, 1, 1, 0, 24)
    t.put("3021.dat", 6, -2, -3, 2, 3, 24, 8, 90)
    t.put("3021.dat", 6, 0, -3, 2, 3, 24, 8, 90)
    if with_back:
        t.put("3010.dat", 6, -2, -1, 4, 1, 32, 24)


bench(T(-100, 260, -90))               # reader bench (west of south path), faces +x
bench(T(200, -100, 180))               # empty bench north of east path, faces +z
bench(T(-200, 120, -90))               # empty bench (faces +x toward plaza, west lawn)

# ---------------------------------------------------------------- playground
# sandbox
G.put("3009.dat", 6, -22, -22, 6, 1, 0, 24)
G.put("3009.dat", 6, -22, -17, 6, 1, 0, 24)
G.put("3010.dat", 6, -22, -21, 1, 4, 0, 24, 90)
G.put("3010.dat", 6, -17, -21, 1, 4, 0, 24, 90)
G.put("3031.dat", 28, -21, -21, 4, 4, 0, 8)
# slide: tower + stepped ramp (+z)
G.put("3003.dat", 14, -14, -22, 2, 2, 0, 24)
G.put("3003.dat", 14, -14, -22, 2, 2, 24, 24)
G.put("3022.dat", 4, -14, -22, 2, 2, 48, 8)
for (z0, nb, npl) in ((-20, 1, 2), (-18, 1, 1), (-16, 1, 0), (-14, 0, 2), (-12, 0, 1)):
    base = 0
    if nb:
        G.put("3003.dat", 1, -14, z0, 2, 2, 0, 24)
        base = 24
    for i in range(npl):
        G.put("3022.dat", 73 if i == npl - 1 else 1, -14, z0, 2, 2, base + 8 * i, 8)
# stairs up to tower (east side)
G.put("3003.dat", 1, -12, -22, 2, 2, 0, 24)
G.put("3022.dat", 73, -12, -22, 2, 2, 24, 8)
G.put("3022.dat", 1, -10, -22, 2, 2, 0, 8)
G.put("3022.dat", 73, -10, -22, 2, 2, 8, 8)
# see-saw
for u in (-8, -7):
    add("3062b.dat", 25, u * 20 + 10, -24, -230)
    add("3062b.dat", 25, u * 20 + 10, -48, -230)
th = math.radians(8)
c, s = math.cos(th), math.sin(th)
pivot = (-140, -48, -230)
org = (pivot[0] + 8 * s, pivot[1] - 8 * c, pivot[2])
add("3460.dat", 14, *org, matrix=[[round(c, 6), round(-s, 6), 0], [round(s, 6), round(c, 6), 0], [0, 0, 1]])
SEESAW_L = (org[0] - 56 * c, org[1] - 56 * s - 8, pivot[2])
SEESAW_R = (org[0] + 56 * c, org[1] + 56 * s - 8, pivot[2])

# ---------------------------------------------------------------- gazebo (NE)
G.put("3032.dat", 15, 13, -19, 6, 4, 0, 8)
G.put("3795.dat", 15, 13, -15, 6, 2, 0, 8)
for (u, v) in ((13, -19), (18, -19), (13, -14), (18, -14)):
    for i in range(5):
        add("3062b.dat", 15, u * 20 + 10, -8 - 24 * (i + 1), v * 20 + 10)
G.put("3032.dat", 4, 13, -19, 6, 4, 128, 8)
G.put("3795.dat", 4, 13, -15, 6, 2, 128, 8)
G.put("3031.dat", 15, 14, -18, 4, 4, 136, 8)
G.put("3022.dat", 4, 15, -17, 2, 2, 144, 8)
add("4589.dat", 14, 16 * 20 - 10, -152 - 24, -17 * 20 + 10)

# ---------------------------------------------------------------- picnic, towel, BBQ (SE)
for dv in range(6):
    for du in range(6):
        G.put("3024.dat", 4 if (du + dv) % 2 == 0 else 15, 12 + du, 12 + dv, 1, 1, 0, 8)
G.put("3003.dat", 6, 16, 13, 2, 2, 8, 24)        # basket
G.put("3024.dat", 25, 16, 13, 1, 1, 32, 8)
G.put("3024.dat", 14, 17, 14, 1, 1, 32, 8)
G.put("3021.dat", 73, 12, 19, 2, 3, 0, 8, 90)     # towel
G.put("3021.dat", 15, 14, 19, 2, 3, 0, 8, 90)
# BBQ
G.put("3003.dat", 0, 21, 13, 2, 2, 0, 24)
G.put("3022.dat", 0, 21, 13, 2, 2, 24, 8)
add("6141.dat", 57, 21 * 20 + 10, -40, 13 * 20 + 10)
add("6141.dat", 57, 22 * 20 + 10, -40, 14 * 20 + 10)
add("6141.dat", 4, 22 * 20 + 10, -40, 13 * 20 + 10)
for i in range(3):
    add("3062b.dat", 47, 21 * 20 + 10 + 20 * (i % 2), -40 - 24 * (i + 1) - 4, 13 * 20 + 10) if False else None
add("3062b.dat", 47, 21 * 20 + 10, -64, 13 * 20 + 10)
add("3062b.dat", 47, 21 * 20 + 10, -88, 13 * 20 + 10)
add("6141.dat", 47, 21 * 20 + 10, -96, 13 * 20 + 10)

# ---------------------------------------------------------------- ice-cream cart
cart = T(120, 200, 90)
cart.put("3032.dat", 71, -3, -2, 6, 4, 0, 8)
cart.put("3010.dat", 4, -2, -2, 4, 1, 8, 24)
cart.put("3010.dat", 15, -2, -2, 4, 1, 32, 24)
for (u, v) in ((-3, -2), (2, -2), (-3, 1), (2, 1)):
    for i in range(5):
        cart.put("3062b.dat", 15, u, v, 1, 1, 8 + 24 * i, 24)
cart.put("3032.dat", 4, -3, -2, 6, 4, 128, 8)
cart.put("3031.dat", 15, -2, -2, 4, 4, 136, 8)

# ---------------------------------------------------------------- sun on a mast (NE corner lawn)
sx, sz = 21 * 20 + 10, -22 * 20 + 10
for i in range(10):
    add("3062b.dat", 15, sx, -24 * (i + 1), sz)
add("3941.dat", 14, sx + 10, -240 - 24, sz + 10)
add("3941.dat", 14, sx + 10, -240 - 48, sz + 10)
add("4589.dat", 25, sx + 10, -240 - 72, sz + 10)

# ================================================================= figures
# name, minifig-plan args, world (x, y, z), yaw
F = []


def fig(n, args, x, y, z, yaw):
    F.append((f"fig{n:02d}", args, (x, y, z), yaw))


KID = ["--legs", "41879b:"]
fig(1, ["--torso", "973:4", "--legs", "41879b:1", "--headwear", "90541:14", "--left-arm", "180", "--right-arm", "180"],
    -260, -56, -410, 180)
fig(2, ["--torso", "973:14", "--legs", "41879b:4", "--headwear", "3901:6", "--left-arm", "120", "--right-arm", "180"],
    -260, -24, -310, 180)
fig(3, ["--torso", "973:25", "--legs", "41879b:1", "--headwear", "43751:0", "--right-item", "18791:7", "--right-arm", "60"],
    -380, -8, -370, 180)
fig(4, ["--torso", "973:2", "--legs", "73200b-f1:1", "--headwear", "6093a:0", "--sit", "--left-arm", "60", "--right-arm", "60"],
    SEESAW_L[0], SEESAW_L[1], SEESAW_L[2], -90)
fig(5, ["--torso", "973:1", "--legs", "73200b-f1:0", "--headwear", "3901:25", "--sit", "--left-arm", "60", "--right-arm", "60"],
    SEESAW_R[0], SEESAW_R[1], SEESAW_R[2], 90)
fig(6, ["--torso", "973:27", "--legs", "41879b:0", "--headwear", "21787:19", "--right-item", "93216:14", "--right-arm", "60"],
    -210, 0, -120, -90)
fig(7, ["--torso", "973:13", "--legs", "73200b-f1:1", "--headwear", "40251:6", "--sit", "--left-item", "3899:15", "--left-arm", "60"],
    300, -8, 310, 0)
fig(8, ["--torso", "973:1", "--legs", "73200b-f1:0", "--headwear", "98279:19", "--sit", "--right-item", "33051:4", "--right-arm", "60"],
    260, -8, 250, 180)
fig(9, ["--torso", "973p2a:15", "--legs", "73200b-f1:0", "--headwear", "98381:15", "--right-item", "4528:0", "--right-arm", "60"],
    370, 0, 280, -90)
fig(10, ["--head", "3626bp7b:14", "--torso", "973p2h:15", "--legs", "73200b-f1:25", "--headwear", "90388:14", "--sit",
         "--right-item", "30222:4", "--right-arm", "60"],
    260, -8, 390, 0)
fig(11, ["--torso", "973:2", "--legs", "73200b-f1:19", "--headwear", "2514:0", "--right-item", "10170:25", "--right-arm", "60"],
    -110, -8, 20, -90)
fig(12, ["--torso", "973:15", "--legs", "73200b-f1:71", "--headwear", "3898:15", "--right-item", "33120:19", "--right-arm", "60"],
    130, -8, 200, 90)
fig(13, ["--torso", "973:25", "--legs", "73200b-f1:6", "--headwear", "10048:6", "--right-item", "33120:4", "--right-arm", "60"],
    30, -8, 200, -90)
fig(14, ["--head", "3626bp7g:14", "--torso", "973:71", "--legs", "73200b-f1:72", "--headwear", "90541:0",
         "--right-item", "30148:0", "--right-arm", "90", "--left-arm", "60"],
    90, -8, -20, 90)
fig(15, ["--torso", "973:27", "--legs", "73200b-f1:1", "--headwear", "6093a:25", "--left-arm", "60", "--right-arm", "-45"],
    -20, -8, -330, 180)
fig(16, ["--head", "3626bp7g:14", "--torso", "973:7", "--legs", "73200b-f1:72", "--headwear", "2514:7",
         "--right-item", "24077:6", "--right-arm", "60"],
    270, -8, -20, -90)
fig(17, ["--torso", "973:13", "--legs", "73200b-f1:1", "--headwear", "43751:71", "--left-item", "33061:15", "--left-arm", "60"],
    230, -8, 20, -90)
fig(18, ["--torso", "973:22", "--legs", "73200b-f1:0", "--headwear", "90388:4", "--right-item", "13808:0", "--right-arm", "60", "--left-arm", "30"],
    320, -8, -330, 180)
fig(19, ["--torso", "973:2", "--legs", "73200b-f1:6", "--headwear", "3901:0", "--sit", "--right-item", "3899:15", "--right-arm", "60"],
    -50, -32, 260, -90)
fig(20, ["--torso", "973:10", "--legs", "73200b-f1:1", "--headwear", "3629:25", "--right-item", "3836:14", "--right-arm", "60"],
    -400, 0, 390, 0)


def make(f):
    name, args, _, _ = f
    out = f"{FIGDIR}/{name}.plan.json"
    if os.path.exists(out):
        return name, True
    cmd = ["./ldraw-agent", "minifig", "plan", name, "--output", out] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAILED", name, r.stderr[-400:] or r.stdout[-400:])
        return name, False
    return name, True


with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(make, F))
bad = [n for n, ok in res if not ok]
if bad:
    sys.exit("figure generation failed: " + ",".join(bad))

includes = []
for (name, args, (x, y, z), yaw) in F:
    includes.append(f"figs/{name}.plan.json")
    add(f"{name}.ldr", 16, x, y, z, yaw, purpose="minifig " + name)

plan = {"version": 1, "author": "LDraw Nova agent (carlos.antelo@gmail.com session)",
        "includes": includes,
        "sections": [{"name": "park.ldr", "description": "Maple Green Park on a sunny day with 20 minifigs",
                      "steps": [P[i:i + 150] for i in range(0, len(P), 150)]}]}
json.dump(plan, open(f"{OUT}/park.plan.json", "w"), indent=1)
print("placements in main:", len(P), "figures:", len(F))


# ---- cropped plans for close-up review renders
CROPS = {"nw": (-480, -20, -480, -20), "ne": (20, 480, -480, -20), "se": (20, 480, 20, 480),
         "sw": (-480, -20, 20, 480), "centre": (-200, 200, -200, 200)}
for nm, (x0, x1, z0, z1) in CROPS.items():
    sel = [q for q in P if x0 <= q["at"][0] <= x1 and z0 <= q["at"][2] <= z1 and not q["ref"].startswith("3867")]
    base = [dict(id="g1", ref="3867.dat", colour=2, at=[(x0+x1)//2//320*320 if False else {"nw":-320,"ne":320,"se":320,"sw":-320,"centre":0}[nm],0,{"nw":-320,"ne":-320,"se":320,"sw":320,"centre":0}[nm]])]
    used = {q["ref"] for q in sel}
    inc = [f"figs/{n}.plan.json" for (n, a, pos, yw) in F if f"{n}.ldr" in used]
    cp = {"version": 1, "author": plan["author"], "includes": inc,
          "sections": [{"name": f"crop-{nm}.ldr", "description": "close-up " + nm,
                        "steps": [base, sel]}]}
    json.dump(cp, open(f"{OUT}/crop-{nm}.plan.json", "w"), indent=1)
