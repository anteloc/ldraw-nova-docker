import sys, json, re, sqlite3
sys.path.insert(0,'.')
import numpy as np
from ldraw_tools.document import parse_source, section_table, is_part
from ldraw_tools.common import get_parts, normalized
PARTS=get_parts()
DB=sqlite3.connect('file:data/ldraw-info.db?mode=ro',uri=True)
def bb(ref):
    r=DB.execute('select min_x,min_y,min_z,max_x,max_y,max_z from PART_BBOXES where alias=?',(ref.lower() if ref.lower().endswith('.dat') else ref.lower()+'.dat',)).fetchone()
    return np.array(r[:3]) if r else None, np.array(r[3:]) if r else None
for ref in ['44771','15038','92909','62821','87761','2851','2850b','2854','18946','18947','18948','6641','2741','2819','3712','92906']:
    lo,hi=bb(ref)
    print(ref, PARTS.by_code.get(ref,'?')[:55], None if lo is None else (lo.round(1).tolist(), hi.round(1).tolist()))
m=parse_source('data/models-annotated/42039-1.mpd'); T=section_table(m)
def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
units={}
def walk(sec,M,t,tag):
    for si,st in enumerate(sec.steps,1):
        for p in st:
            if not hasattr(p,'reference'): continue
            Mc,tc=M@mat(p),M@vec(p)+t
            ch=T.get(normalized(p.reference))
            tg=tag if tag else (ch.name if ch is not None and not is_part(ch) else f'main-step{si}')
            if ch is not None and not is_part(ch): walk(ch,Mc,tc,tg)
            else:
                lo,hi=bb(p.reference)
                if lo is None: lo,hi=np.zeros(3),np.zeros(3)
                corners=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
                w=(Mc@corners.T).T+tc
                u=units.setdefault(tg,[np.full(3,1e9),np.full(3,-1e9),0])
                u[0]=np.minimum(u[0],w.min(0)); u[1]=np.maximum(u[1],w.max(0)); u[2]+=1
walk(m,np.eye(3),np.zeros(3),None)
for k in ['42039 - frontaxle.ldr','42039 - steeringrack.ldr','42039 - frontaxletop.ldr','42039 - motor.ldr','42039 - seat.ldr','main-step2','main-step1','main-step3','main-step4','main-step5','main-step34','main-step35','42039 - doorlift2.ldr']:
    if k in units:
        lo,hi,n=units[k]; print(f'{k:32s} n={n:3d} X {lo[0]:.0f}..{hi[0]:.0f}  Y {lo[1]:.0f}..{hi[1]:.0f}  Z {lo[2]:.0f}..{hi[2]:.0f}')
allo=np.min([u[0] for u in units.values()],0); alhi=np.max([u[1] for u in units.values()],0)
print('42039 solid bounds', allo.round(0), alhi.round(0))
