p='output/city-park/generate.py'
s=open(p).read()
a=s.index("cart = T(120, 200, 90)"); b=s.index("# ---------------------------------------------------------------- sun")
s=s[:a]+'''cart = T(120, 200, 90)
cart.put("3032.dat", 71, -3, -2, 6, 4, 0, 8)
cart.put("3010.dat", 4, -2, -2, 4, 1, 8, 24)
cart.put("3010.dat", 15, -2, -2, 4, 1, 32, 24)
for (u, v) in ((-3, -2), (2, -2), (-3, 1), (2, 1)):
    for i in range(5):
        cart.put("3062b.dat", 15, u, v, 1, 1, 8 + 24 * i, 24)
cart.put("3032.dat", 4, -3, -2, 6, 4, 128, 8)
cart.put("3031.dat", 15, -2, -2, 4, 4, 136, 8)

'''+s[b:]
s=s.replace('G.put("3003.dat", 6, 14, 13, 2, 2, 8, 24)        # basket\nG.put("3024.dat", 25, 14, 13, 1, 1, 32, 8)\nG.put("3024.dat", 14, 15, 14, 1, 1, 32, 8)',
 'G.put("3003.dat", 6, 16, 13, 2, 2, 8, 24)        # basket\nG.put("3024.dat", 25, 16, 13, 1, 1, 32, 8)\nG.put("3024.dat", 14, 17, 14, 1, 1, 32, 8)')
s=s.replace("-260, -48, -410, 180)","-260, -56, -410, 180)")
s=s.replace("260, -8, 210, 180)","260, -8, 250, 180)")
s=s.replace("    50, 0, 200, -90)","    30, -8, 200, -90)")
s=s.replace("    390, 0, 280, -90)","    370, 0, 280, -90)")
s=s.replace("SEESAW_L = (org[0] - 56 * c, org[1] - 56 * s, pivot[2])","SEESAW_L = (org[0] - 56 * c, org[1] - 56 * s - 8, pivot[2])")
s=s.replace("SEESAW_R = (org[0] + 56 * c, org[1] + 56 * s, pivot[2])","SEESAW_R = (org[0] + 56 * c, org[1] + 56 * s - 8, pivot[2])")
open(p,'w').write(s)
import subprocess
print(subprocess.run('''.venv/bin/python output/city-park/generate.py 2>&1|tail -2; ./ldraw-agent build output/city-park/park.plan.json --force 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['checks_passed'],d['written']);[print(json.dumps(x)[:400]) for x in d['diagnostics'] if x['severity']=='error']"; ./ldraw-agent minifig check output/city-park/park.mpd 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in d['diagnostics']:
    if x['code'].startswith('minifig'): print(x['code'],x.get('figure',x.get('instance')),x.get('parts'),x.get('obstacle'),x.get('depth_ldu'))
for f in d['figures']:
    if not f['support']: print('nosupport',f['section'])
"''',shell=True,capture_output=True,text=True).stdout)