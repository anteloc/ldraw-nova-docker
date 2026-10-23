p='output/city-park/generate.py'
s=open(p).read()
s+='''

# ---- cropped plans for close-up review renders
CROPS = {"nw": (-480, -20, -480, -20), "ne": (20, 480, -480, -20), "se": (20, 480, 20, 480),
         "sw": (-480, -20, 20, 480), "centre": (-200, 200, -200, 200)}
for nm, (x0, x1, z0, z1) in CROPS.items():
    sel = [q for q in P if x0 <= q["at"][0] <= x1 and z0 <= q["at"][2] <= z1 and not q["ref"].startswith("3867")]
    base = [q for q in P if q["ref"].startswith("3867")]
    used = {q["ref"] for q in sel}
    inc = [f"figs/{n}.plan.json" for (n, a, pos, yw) in F if f"{n}.ldr" in used]
    cp = {"version": 1, "author": plan["author"], "includes": inc,
          "sections": [{"name": f"crop-{nm}.ldr", "description": "close-up " + nm,
                        "steps": [base, sel]}]}
    json.dump(cp, open(f"{OUT}/crop-{nm}.plan.json", "w"), indent=1)
'''
open(p,'w').write(s)
import subprocess
print(subprocess.run('.venv/bin/python output/city-park/generate.py 2>&1|tail -3; for n in nw ne se sw centre; do ./ldraw-agent build output/city-park/crop-$n.plan.json --force 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\'checks_passed\'],d[\'written\'])"; ./ldraw-agent render output/city-park/crop-$n.mpd --outdir output/city-park/crops/$n 2>&1 | tail -2; done; ls output/city-park/crops/*',shell=True,capture_output=True,text=True).stdout)