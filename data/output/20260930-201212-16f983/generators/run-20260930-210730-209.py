import sys, re, sqlite3
sys.path.insert(0,'.')
import numpy as np
from collections import defaultdict
from ldraw_tools.document import parse_source, section_table, is_part
from ldraw_tools.common import get_parts, normalized
PARTS=get_parts()
m=parse_source('data/models-annotated/42039-1.mpd'); T=section_table(m)
def mat(p): return np.array([[float(v) for v in r] for r in getattr(p.matrix,'rows',p.matrix)])
def vec(p): v=p.position; return np.array([float(v.x),float(v.y),float(v.z)])
def dump(secname, origin, zsplit=None, show=40):
    sec=T[normalized(secname)]
    rows=[]
    def walk(s,M,t):
        for p in s.pieces:
            Mc,tc=M@mat(p),M@vec(p)+t
            ch=T.get(normalized(p.reference))
            if ch is not None and not is_part(ch): walk(ch,Mc,tc)
            else: rows.append((p.reference.lower(), PARTS.by_code.get(normalized(p.reference).removesuffix('.dat'),'')[:44], (tc+origin).round(0)))
    walk(sec,np.eye(3),np.zeros(3))
    return rows
# motor in donor world (origin 0,-130,540) -> ours (+0,+20,+60)
rows=dump('42039 - motor.ldr', np.array([0,-110,600]))
for r in sorted(rows,key=lambda r:r[2][2]):
    if re.search('Piston|Crank|Cylinder|Axle|Gear|Joiner|Bush',r[1]): print('MOTOR',r[0],r[1],r[2].tolist())
rows=dump('42039 - frontaxle.ldr', np.array([0,-60,0]))
for r in sorted(rows,key=lambda r:-r[2][2])[:14]: print('FAXLE',r[0],r[1],r[2].tolist())
rows=dump('42039 - frontaxletop.ldr', np.array([0,-140,-20]))
for r in rows:
    if re.search('Gear|Axle|Steering|Joint|Knob',r[1]): print('FTOP',r[0],r[1],r[2].tolist())
