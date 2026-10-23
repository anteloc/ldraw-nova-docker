p='output/city-park/generate.py'
s=open(p).read()
s=s.replace('base = [q for q in P if q["ref"].startswith("3867")]','base = [dict(id="g1", ref="3867.dat", colour=2, at=[(x0+x1)//2//320*320 if False else {"nw":-320,"ne":320,"se":320,"sw":-320,"centre":0}[nm],0,{"nw":-320,"ne":-320,"se":320,"sw":320,"centre":0}[nm]])]')
open(p,'w').write(s)
import subprocess
print(subprocess.run('.venv/bin/python output/city-park/generate.py 2>&1|tail -3; for n in nw ne se sw centre; do ./ldraw-agent build output/city-park/crop-$n.plan.json --force 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\'checks_passed\'],d[\'written\'])"; ./ldraw-agent render output/city-park/crop-$n.mpd --outdir output/city-park/crops/$n >/dev/null 2>&1; done',shell=True,capture_output=True,text=True).stdout)