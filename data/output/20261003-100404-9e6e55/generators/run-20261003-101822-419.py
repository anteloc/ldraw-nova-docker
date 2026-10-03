import os, sys
print("cwd:", os.getcwd())
print("path:", sys.path)
try:
    import pyldraw3
    print("pyldraw3 ok:", pyldraw3.__file__)
except Exception as e:
    print("import fail:", e)
import subprocess
print(subprocess.run(["find", "/data", "-maxdepth", "3", "-name", "pyldraw3", "-type", "d"], capture_output=True, text=True).stdout[:500])
