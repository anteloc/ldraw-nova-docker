import sys; sys.path.insert(0,'output/generators')
import fz, numpy as np
for r in ['32278','64178','32526','60484','32333','62462','44294','6587','32269','32270','94925','18946','35185','18948','18947','32073','4519','3713','6641','32140']:
    lo,hi=fz.bounds(r); print(r, fz.desc(r)[:44], lo.round(1).tolist(), hi.round(1).tolist())
c=fz.connectors('32278'); print(len(c)); print(c[0] if c else None)
