import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
rows=fz.load_donor()
def show(r):
    M=r['M']; hole=M@np.array([0,1,0]); long_=M@np.array([0,0,1]); x=M@np.array([1,0,0])
    f=lambda v:'('+','.join(f'{a:+.0f}' for a in v)+')'
    print(f"s{r['step']:<3}{r['ref']:10s}{str([round(v) for v in r['pos']]):22s} localX->{f(x)} localY->{f(hole)} localZ->{f(long_)}  {r['desc'][:40]}")
for r in rows:
    if r['step'] in (1,10) and r['ref'] in ('64178.dat','60484.dat','6587.dat','32526.dat','32140.dat'): show(r)
    if r['step'] in (11,14,15,19,20,21) and r['ref'] in ('32278.dat','41239.dat','32526.dat','55615.dat','40490.dat'): show(r)
