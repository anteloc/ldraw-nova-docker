
import re,collections
L=[l.split() for l in open('output/uploads/1d4b95e71ea64234959f38064b6b7924/0/Naganata-ann.mpd') if l.startswith('1 ')]
c=collections.Counter(l[-1] for l in L)
print(len(L));print(c.most_common(60))
xs=[float(l[2]) for l in L];ys=[float(l[3]) for l in L];zs=[float(l[4]) for l in L]
print(min(xs),max(xs),min(ys),max(ys),min(zs),max(zs))
