import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
from ldraw_tools.common import jsonable
cs=[jsonable(c) for c in fz.geom('64178').connections]
axes={}
for c in cs:
    a=tuple(np.round(np.array(c['frame'])[:,1]).astype(int)); p=tuple(np.round(c['position']).astype(int))
    axes.setdefault(a,set()).add(p)
for a,ps in axes.items():
    ps=sorted(ps); print(a, len(ps), ps[:40])
