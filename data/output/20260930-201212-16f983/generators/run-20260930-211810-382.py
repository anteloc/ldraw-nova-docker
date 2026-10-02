import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
from ldraw_tools.common import jsonable
g=fz.geom('32278'); c=g.connections
print(len(c)); import json
d=jsonable(c[0]); print(json.dumps(d)[:900])
kinds={}
for x in c:
    j=jsonable(x); k=(j.get('kind'),j.get('gender') if 'gender' in j else None)
    kinds[str(k)]=kinds.get(str(k),0)+1
print(kinds)
