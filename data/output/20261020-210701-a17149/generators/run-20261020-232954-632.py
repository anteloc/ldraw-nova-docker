p='output/city-park/generate.py'
s=open(p).read()
s=s.replace("(9, 19, 2)","(5, 19, 2)")
s=s.replace('add("3941.dat", 14, sx, -240 - 24, sz + 0) if False else None','''add("3941.dat", 14, sx + 10, -240 - 24, sz + 10)
add("3941.dat", 14, sx + 10, -240 - 48, sz + 10)
add("4589.dat", 25, sx + 10, -240 - 72, sz + 10)''')
open(p,'w').write(s)
import subprocess
print(subprocess.run('.venv/bin/python output/city-park/generate.py 2>&1|tail -2; ./ldraw-agent build output/city-park/park.plan.json --force 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\'checks_passed\'],d[\'written\']);[print(json.dumps(x)[:400]) for x in d[\'diagnostics\'] if x[\'severity\']==\'error\']"; ./ldraw-agent minifig check output/city-park/park.mpd 2>&1 | python3 -c "\nimport sys,json\nd=json.load(sys.stdin)\nprint({k:(v if not isinstance(v,(list,dict)) else len(v)) for k,v in d.items()})\nfor x in d.get(\'diagnostics\',[]): print(x[\'severity\'],x[\'code\'],x.get(\'message\',\'\')[:130], x.get(\'figure\',\'\'))\n"',shell=True,capture_output=True,text=True))