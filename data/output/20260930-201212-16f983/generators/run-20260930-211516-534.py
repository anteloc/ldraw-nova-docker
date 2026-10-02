import json, numpy as np
rows=json.load(open('output/phase3/donor-42039-carframe.json'))
def axes(r):
    M=np.array(r['mat']); return 'XYZ'[int(np.abs(M[:,0]).argmax())]+'XYZ'[int(np.abs(M[:,1]).argmax())]+'XYZ'[int(np.abs(M[:,2]).argmax())]
for r in rows:
    x,y,z=r['pos']
    if 560<=z<=730 and abs(x)<=40 and ('Gear' in r['desc'] or 'Axle' in r['desc'] or 'Joiner' in r['desc'] or 'Bush' in r['desc']):
        print(f"s{r['step']:<3}{r['unit'][:14]:14s} {r['ref']:10s} {str(r['pos']):24s} {axes(r)} {r['desc'][:44]}")
