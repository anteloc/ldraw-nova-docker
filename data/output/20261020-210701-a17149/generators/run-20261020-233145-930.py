p='output/city-park/generate.py'
s=open(p).read()
s=s.replace("    110, -8, 200, 90)","    130, -8, 200, 90)")
open(p,'w').write(s)
import subprocess
print(subprocess.run('''.venv/bin/python output/city-park/generate.py 2>&1|tail -2; ./ldraw-agent build output/city-park/park.plan.json --force 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['checks_passed'],d['written'])"; ./ldraw-agent minifig check output/city-park/park.mpd 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in d['diagnostics']:
    if x['code'].startswith('minifig'): print(x['code'],x.get('figure',x.get('instance')),x.get('parts'),x.get('obstacle'),x.get('depth_ldu'))
"''',shell=True,capture_output=True,text=True).stdout)