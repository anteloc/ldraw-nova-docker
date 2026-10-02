import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np, json
from ldraw_tools.common import jsonable
for ref in ['2780','3705','32278','64178','60484']:
    cs=[jsonable(c) for c in fz.geom(ref).connections]
    kinds={}
    for c in cs: kinds[c['kind']]=kinds.get(c['kind'],0)+1
    ex=[c for c in cs if c['kind'] in ('pin','axle','pin_hole','axle_hole')][:2]
    print(ref, kinds, [(c['kind'],c['position'],[row[1] for row in c['frame']]) for c in ex])
