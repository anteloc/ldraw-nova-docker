import sys, json, re, subprocess, collections
sys.path.insert(0,'.'); sys.path.insert(0,'output/generators')
import numpy as np
from pathlib import Path
from ldraw_tools.document import parse_source, section_table, is_part
from ldraw_tools.common import get_parts, normalized
import fz
def proper(M):
    U,S,Vt=np.linalg.svd(M); R=U@Vt
    if np.linalg.det(R)<0: U[:,-1]*=-1; R=U@Vt
    R[np.abs(R)<1e-9]=0; 
    for v in (1,-1):
        R[np.abs(R-v)<1e-9]=v
    return R
m=parse_source('data/models-annotated/42039-1.mpd'); T=section_table(m)
def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
rows=[]; maxerr=0
def walk(sec,M,t,top,step,colour=16):
    global maxerr
    for si,st in enumerate(sec.steps,1):
        for p in st:
            if not hasattr(p,'reference'): continue
            R=mat(p); Rp=proper(R); maxerr=max(maxerr,np.abs(R-Rp).max())
            Mc,tc=M@Rp,M@vec(p)+t
            code=p.colour.code if p.colour.code!=16 else colour
            ch=T.get(normalized(p.reference))
            s = si if top is None else step
            unit = (ch.name if (top is None and ch is not None and not is_part(ch)) else top)
            if ch is not None and not is_part(ch): walk(ch,Mc,tc,unit,s,code)
            else:
                ref=p.reference.lower()
                if ref.startswith('42039 - 33299b'): ref='33299b.dat'
                rows.append(dict(ref=ref,desc=fz.desc(ref),colour=code,pos=(tc+fz.DONOR_SHIFT).tolist(),mat=Mc.tolist(),step=s,unit=unit or 'main'))
walk(m,np.eye(3),np.zeros(3),None,None)
print('max rotation correction', maxerr)
json.dump(rows,open('output/phase3/donor-42039-carframe.json','w'))
rows=fz.load_donor()
sel=[r for r in rows if r['step']<=21 and 'RibHose' not in r['unit']]
def line(r):
    M=r['M']; t=r['t']
    return f"1 {r['colour']} {t[0]:.4f} {t[1]:.4f} {t[2]:.4f} "+' '.join(f'{v:.9f}' for v in M.flatten())+f" {r['ref']}"
body=['0 FILE donor-rear.ldr','0 42039 steps 1-21 in car frame (review copy, springs/hoses removed)','0 Name: donor-rear.ldr','0 Author: The LEGO Group model 42039 as annotated in data/models-annotated (review copy by agent)','0 !LDRAW_ORG Model']+[line(r) for r in sel]+['0 NOFILE']
p=Path('output/phase3/donor/donor-rear.mpd'); p.write_text('\r\n'.join(body)+'\r\n',encoding='utf-8')
r=subprocess.run(['./ldraw-agent','inspect',str(p),'--contacts','all','--detail','full','--limit','500','--report','output/phase3/donor/donor-rear.inspect.json'],capture_output=True,text=True)
d=json.load(open('output/phase3/donor/donor-rear.inspect.json'))
print('exit',r.returncode, collections.Counter((x['code'],x['severity']) for x in d.get('diagnostics',[])).most_common(8))
g=d['geometry']; print('contacts',g['contact_count'],'truncated',g['contacts_truncated'],'confirmed comps',g['confirmed_component_count'],'optimistic',g['optimistic_component_count'])
print(json.dumps(g['contacts'][0])[:600])
