import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
rows=fz.load_donor()
ax=lambda r:'XYZ'[int(np.abs(r['M']@[1,0,0]).argmax())]
for st in [23,24,25,26,12,13]:
    print('--- step',st, ' '.join(f"{r['ref'][:-4]}@{[round(v) for v in r['pos']]}{ax(r)}" for r in rows if r['step']==st and r['unit']=='main'))
