import sys, json, re
sys.path.insert(0,'.')
import numpy as np
from collections import Counter
from pathlib import Path
from ldraw_tools.document import parse_source, section_table, is_part
from ldraw_tools.common import get_parts, normalized
PARTS=get_parts()
D=np.array([0,20,60])
m=parse_source('data/models-annotated/42039-1.mpd'); T=section_table(m)
print('embedded DATs:', [s.name for s in T.values() if is_part(s)])
def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
rows=[]
def walk(sec,M,t,top,step,colour=16):
    for si,st in enumerate(sec.steps,1):
        for p in st:
            if not hasattr(p,'reference'): continue
            Mc,tc=M@mat(p),M@vec(p)+t
            code=p.colour.code if p.colour.code!=16 else colour
            ch=T.get(normalized(p.reference))
            s = si if top is None else step
            unit = (ch.name if (top is None and ch is not None and not is_part(ch)) else top)
            if ch is not None and not is_part(ch):
                walk(ch,Mc,tc,unit,s,code)
            else:
                d=PARTS.by_code.get(normalized(p.reference).removesuffix('.dat'),'') or (ch.description if ch else '')
                rows.append(dict(ref=p.reference.lower(),desc=d,colour=code,pos=(tc+D).round(1).tolist(),mat=Mc.round(4).tolist(),step=s,unit=unit or 'main'))
walk(m,np.eye(3),np.zeros(3),None,None)
Path('output/phase3').mkdir(parents=True,exist_ok=True)
json.dump(rows,open('output/phase3/donor-42039-carframe.json','w'))
for st in range(1,46):
    rs=[r for r in rows if r['step']==st]
    if not rs: continue
    P=np.array([r['pos'] for r in rs]); units=Counter(r['unit'] for r in rs)
    top=Counter(r['ref'] for r in rs).most_common(4)
    print(f"s{st:2d} n={len(rs):3d} X{P[:,0].min():5.0f}..{P[:,0].max():4.0f} Y{P[:,1].min():5.0f}..{P[:,1].max():4.0f} Z{P[:,2].min():5.0f}..{P[:,2].max():4.0f} {dict(units) if len(units)>1 or 'main' not in units else ''} {top}")
