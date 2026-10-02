import sys; sys.path.insert(0,'output/generators')
import fz, joins, numpy as np, collections
rows=[r for r in fz.load_donor() if r['step']<=21 and 'RibHose' not in r['unit']]
def grp(r):
    if 'motor' in r['unit']: return 'MOTOR'
    if r['step']<=10: return 'REAR'
    return f"F{r['step']}"
J=joins.joins(rows)
cross=collections.defaultdict(list)
for i,hit in J:
    gs={grp(rows[j]) for j in hit}|{grp(rows[i])}
    if len(gs)>1 and ('MOTOR' in gs or 'REAR' in gs):
        cross[tuple(sorted(gs))].append((rows[i]['ref'],[round(v) for v in rows[i]['pos']],[ (rows[j]['ref'],grp(rows[j])) for j in hit]))
for k,v in sorted(cross.items()):
    print('==',k,len(v))
    for e in v[:6]: print('   ',e)
