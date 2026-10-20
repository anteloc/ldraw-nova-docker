
import re, pathlib
lib = pathlib.Path("/opt/ldraw/ldraw/parts")
def tri_bounds(fn, depth=0, seen=None, mat=None):
    # crude recursive bounds from type 1 (subfiles) and type 3/4 (polygons), identity transforms only for estimate
    pass
import subprocess, json
for p in ["3037.dat","3040b.dat","3039.dat"]:
    out = subprocess.run(["/opt/ldraw-nova/.venv/bin/python","-c","print(1)"],capture_output=True,text=True) if False else None
print("ok")
