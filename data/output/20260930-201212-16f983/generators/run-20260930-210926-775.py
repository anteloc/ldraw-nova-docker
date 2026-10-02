import sys, json, re, subprocess
sys.path.insert(0,'.')
import numpy as np
from pathlib import Path
from ldraw_tools.document import parse_source, section_table, is_part, source_blocks
from ldraw_tools.common import get_parts, normalized
PARTS=get_parts()
out=Path('output/prospect/rough'); out.mkdir(parents=True, exist_ok=True)
# extra extractions
for sec,ns in [('42039 - frontaxletop.ldr','rl-ftop'),('42039 - shock-06_5L-hard-1.ldr','rl-rshock')]:
    r=subprocess.run(['./ldraw-agent','extract','data/models-annotated/42039-1.mpd','--section',sec,'--namespace',ns,'--output',str(out/f'{ns}.mpd'),'--normalize-rotations','--repair-bfc-comments','--force'],capture_output=True,text=True)
    print(ns,'exit',r.returncode, json.loads(r.stdout).get('root') if r.stdout.strip().startswith('{') else r.stderr[-200:])
# local bounds helper for an extracted mpd root
def local_leaves(path):
    m=parse_source(path); T=section_table(m); rows=[]
    def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
    def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
    def walk(s,M,t):
        for p in s.pieces:
            Mc,tc=M@mat(p),M@vec(p)+t; ch=T.get(normalized(p.reference))
            if ch is not None and not is_part(ch): walk(ch,Mc,tc)
            else: rows.append((p.reference.lower(),PARTS.by_code.get(normalized(p.reference).removesuffix('.dat'),'')[:40],tc.round(1),Mc.round(3)))
    walk(m,np.eye(3),np.zeros(3)); return rows
g=local_leaves('output/prospect/shortlist/m3-gbx-42112.mpd')
P=np.array([r[2] for r in g]); print('42112 gearshift local origin bounds',P.min(0),P.max(0))
for r in g:
    if re.search('Gear|Ring|Joiner|Axle',r[1]): print('  ',r[0],r[1],r[2].tolist(),'longZ->',np.abs(r[3][:,2]).argmax())
s=local_leaves('output/prospect/shortlist/m7-seat-42039.mpd'); P=np.array([r[2] for r in s]); print('seat local origins',P.min(0),P.max(0))
