import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
rows=fz.load_donor()
seat=[r for r in rows if 'seat' in r['unit']]
for r in seat: print(r['ref'], r['colour'], [round(v) for v in r['t']], r['desc'][:50])
P=np.array([fz.world_aabb(r['ref'],r['M'],r['t']) for r in seat]); print('seat bbox', P[:,0].min(0).round(), P[:,1].max(0).round())
print('seat step', seat[0]['step'])
