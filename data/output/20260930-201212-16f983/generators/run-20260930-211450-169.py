import json, numpy as np
rows=json.load(open('output/phase3/donor-42039-carframe.json'))
def ax(r):
    M=np.array(r['mat']); return 'XYZ'[int(np.abs(M[:,0]).argmax())]+'/'+'XYZ'[int(np.abs(M[:,2]).argmax())]
for st in [1,2,10,15,19,20,11,14]:
    print('--- step',st)
    for r in rows:
        if r['step']==st and r['unit']=='main':
            print(f"  {r['ref']:12s} c{r['colour']:<3} {str(r['pos']):26s} {ax(r)} {r['desc'][:46]}")
print('--- motor parts with y>-80 or z>590 (mount/driveline candidates)')
for r in rows:
    if r['unit']=='42039 - motor.ldr' and (r['pos'][1]>-75 or r['pos'][2]>590):
        print(f"  {r['ref']:12s} c{r['colour']:<3} {str(r['pos']):26s} {ax(r)} {r['desc'][:46]}")
