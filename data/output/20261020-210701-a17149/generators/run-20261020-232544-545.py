p='output/city-park/generate.py'
s=open(p).read()
old=s[s.index("# stairs up to tower"):s.index("# see-saw")]
new='''# stairs up to tower (east side)
G.put("3003.dat", 1, -12, -22, 2, 2, 0, 24)
G.put("3022.dat", 73, -12, -22, 2, 2, 24, 8)
G.put("3022.dat", 1, -10, -22, 2, 2, 0, 8)
G.put("3022.dat", 73, -10, -22, 2, 2, 8, 8)
'''
s=s.replace(old,new).replace("flowerbed(3, -9)","flowerbed(7, -9)")
open(p,'w').write(s)
import subprocess
print(subprocess.run('.venv/bin/python output/city-park/generate.py 2>&1 | tail -3; ./ldraw-agent build output/city-park/park.plan.json --force 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\'checks_passed\'],d[\'written\']);[print(json.dumps(x)[:500]) for x in d[\'diagnostics\'] if x[\'severity\']==\'error\']"',shell=True,capture_output=True,text=True).stdout)