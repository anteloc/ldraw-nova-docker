import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
rows=fz.load_donor()
def ax(r):
    M=r['M']; return 'XYZ'[int(np.abs(M@[1,0,0]).argmax())]
for st in [22,30,31,33]:
    print('--- step',st)
    for r in rows:
        if r['step']==st and r['unit']=='main':
            print(f"  {r['ref']:10s} c{r['colour']:<3} {str([round(v) for v in r['pos']]):20s} X->{ax(r)} {r['desc'][:44]}")
print('--- frontaxletop + steeringrack gears/axles')
for r in rows:
    if r['unit'] in ('42039 - frontaxletop.ldr','42039 - steeringrack.ldr') and any(k in r['desc'] for k in ('Gear','Axle','Joint','Knob','Rack')):
        print(f"  {r['unit'][8:20]:12s}{r['ref']:10s} {str([round(v) for v in r['pos']]):20s} X->{ax(r)} {r['desc'][:44]}")
