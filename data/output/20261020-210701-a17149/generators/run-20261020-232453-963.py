import re
p='output/city-park/generate.py'
s=open(p).read()
s=s.replace('"72824:15"','"93216:14"').replace('"4094b:4"','"24077:6"').replace('"80716:6"','"13808:0"').replace('"33009-f1:1"','"3899:15"').replace('"79736:14"','"3836:14"')
# elder B: cup instead of crutch
s=s.replace('"--left-item", "24077:6", "--left-arm", "60"],\n    230','"--left-item", "33061:15", "--left-arm", "60"],\n    230')
open(p,'w').write(s)
import subprocess,os
for f in os.listdir('output/city-park/figs'): pass
print(subprocess.run('.venv/bin/python output/city-park/generate.py 2>&1 | tail -20',shell=True,capture_output=True,text=True).stdout)