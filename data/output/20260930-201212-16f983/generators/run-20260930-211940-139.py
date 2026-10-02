import sys, json, subprocess, collections
sys.path.insert(0,'output/generators')
import fz, numpy as np
from pathlib import Path
rows=fz.load_donor()
print('33299b in library:', bool(fz.desc('33299b')), fz.desc('33299b')[:50], '| embedded users:', collections.Counter(r['step'] for r in rows if '33299' in r['ref']))
sel=[r for r in rows if r['step']<=21 and 'RibHose' not in r['unit']]
def line(r):
    M=r['M']; t=r['t']; ref=r['ref']
    if ref.startswith('42039 - '): ref=ref[8:]
    return f"1 {r['colour']} {t[0]:g} {t[1]:g} {t[2]:g} "+' '.join(f'{v:.6g}' for v in M.flatten())+f" {ref}"
body=['0 FILE donor-rear.ldr','0 42039 steps 1-21 in car frame (review copy, springs/hoses removed)','0 Name: donor-rear.ldr','0 Author: The LEGO Group model 42039 as annotated in data/models-annotated (review copy by agent)','0 !LDRAW_ORG Model']
tag=[]
for r in sel:
    body.append(line(r)); tag.append(dict(step=r['step'],unit=r['unit'],ref=r['ref'],pos=r['pos']))
body.append('0 NOFILE')
p=Path('output/phase3/donor/donor-rear.mpd'); p.write_text('\r\n'.join(body)+'\r\n',encoding='utf-8')
json.dump(tag,open('output/phase3/donor/donor-rear.tags.json','w'))
r=subprocess.run(['./ldraw-agent','inspect',str(p),'--contacts','all','--detail','full','--limit','500','--report','output/phase3/donor/donor-rear.inspect.json'],capture_output=True,text=True)
d=json.load(open('output/phase3/donor/donor-rear.inspect.json'))
print('exit',r.returncode, len(sel), [k for k in d.keys()][:30])
print(collections.Counter((x['code'],x['severity']) for x in d.get('diagnostics',[])).most_common(8))
