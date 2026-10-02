import sys; sys.path.insert(0,'.')
import numpy as np
from ldraw_tools.document import parse_source, section_table, is_part
m=parse_source('data/models-annotated/42056-1.mpd'); T=section_table(m)
def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
found=0
for s in T.values():
    ps=[p for p in s.pieces]
    rings=[p for p in ps if p.reference.lower()=='18947.dat']; catches=[p for p in ps if p.reference.lower()=='6641.dat']
    for r in rings:
        for c in catches:
            d=vec(c)-vec(r)
            if np.linalg.norm(d)<60:
                Rl=mat(r).T@mat(c); dl=mat(r).T@d
                print(s.name, 'catch rel to ring: t', dl.round(1), 'R', np.round(Rl).astype(int).tolist())
                found+=1
                others=[(p.reference, (mat(r).T@(vec(p)-vec(r))).round(0).tolist()) for p in ps if np.linalg.norm(vec(p)-vec(c))<45 and p is not c and p is not r]
                print('   near catch:', others[:8])
    if found>=3: break
