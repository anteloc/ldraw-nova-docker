import sys; sys.path.insert(0,'output/generators')
import fz, collections
rows=fz.load_donor()
for r in rows:
    if r['ref'] in ('15038.dat','44771.dat','4255.dat'): print(r['step'], r['unit'][:30], r['ref'], [round(v,1) for v in r['pos']], r['colour'])
print(fz.desc('32494'), '|', fz.desc('32015'), '|', fz.desc('70038'))
print(collections.Counter(r['colour'] for r in rows if r['step']<=33))
