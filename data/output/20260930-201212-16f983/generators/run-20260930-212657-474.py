import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
from ldraw_tools.common import jsonable
rows=fz.load_donor()
b=[r for r in rows if r['ref']=='32333.dat' and 'motor' in r['unit']][0]
print('32333 world', [round(v,1) for v in b['pos']], np.round(b['M']).astype(int).tolist())
cs=[jsonable(c) for c in fz.geom('32333').connections]
pts=set()
for c in cs:
    a=np.round(np.array(c['frame'])[:,1]).astype(int)
    if c['kind'] in ('pin_hole','axle_hole'):
        w=b['M']@np.array(c['position'])+b['t']; wa=b['M']@a
        pts.add((c['kind'], tuple(np.round(w).astype(int)), tuple(np.round(wa).astype(int))))
for p in sorted(pts, key=lambda q:(q[2],q[1])): print(p)
