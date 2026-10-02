import sys, json, re
sys.path.insert(0,'.')
import numpy as np
from collections import Counter, defaultdict
from ldraw_tools.document import parse_source, section_table, is_part
from ldraw_tools.common import get_parts, normalized
PARTS=get_parts()
m=parse_source('data/models-annotated/42039-1.mpd')
T=section_table(m)
def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
leaves=[]; placements=[]
def walk(sec,M,t,path,colour=16,step=None,depth=0):
    for si,st in enumerate(sec.steps,1):
        for p in st:
            if not hasattr(p,'reference'): continue
            Mc,tc=M@mat(p),M@vec(p)+t
            code=p.colour.code if p.colour.code!=16 else colour
            ch=T.get(normalized(p.reference))
            if ch is not None and not is_part(ch):
                placements.append(dict(section=ch.name,parent=sec.name,pos=tc.round(1).tolist(),mat=Mc.round(3).tolist(),step=si if depth==0 else step))
                walk(ch,Mc,tc,path+[ch.name],code,si if depth==0 else step,depth+1)
            else:
                d=PARTS.by_code.get(normalized(p.reference).removesuffix('.dat'),'') or (ch.description if ch else '')
                leaves.append(dict(ref=p.reference.lower(),desc=d,pos=tc,mat=Mc,colour=code,sec=sec.name,step=si if depth==0 else step))
walk(m,np.eye(3),np.zeros(3),[m.name])
P=np.array([l['pos'] for l in leaves]); lo,hi=P.min(0),P.max(0)
print('42039 origin bounds', lo.round(0), hi.round(0), 'size', (hi-lo).round(0), 'n', len(leaves))
wh=[l for l in leaves if re.search(r'Tyre|Tire|^Wheel|Rim',l['desc'])]
for l in wh: print('WHEEL', l['ref'], l['desc'][:50], l['pos'].round(1), 'axis->', np.abs(l['mat']).argmax(0), l['sec'][:30])
for pl in placements:
    if pl['parent']==m.name or pl['section'] in ('42039 - steeringrack.ldr',):
        print('PLACE', pl['section'][:40], pl['pos'], 'step', pl['step'], 'mat', pl['mat'])
# colour of lights for front direction
for code,name in [(36,'trans red'),(47,'trans clear'),(46,'trans yellow')]:
    z=[l['pos'][2] for l in leaves if l['colour']==code]
    if z: print(name, len(z), 'mean z', round(np.mean(z),1))
json.dump(dict(bounds=[lo.tolist(),hi.tolist()],placements=placements,wheels=[dict(ref=l['ref'],desc=l['desc'],pos=l['pos'].tolist(),mat=l['mat'].tolist()) for l in wh]),open('output/prospect/measure-42039.json','w'),indent=1)
