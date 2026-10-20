import sys,re
src,dst,x0,x1,z0,z1=sys.argv[1],sys.argv[2],*map(float,sys.argv[3:7])
out=[]
for l in open(src,encoding='utf8',newline=''):
    t=l.split()
    if t and t[0]=='1' and len(t)>=15:
        x,z=float(t[2]),float(t[4])
        if not(x0<=x<=x1 and z0<=z<=z1): continue
    out.append(l)
open(dst,'w',encoding='utf8',newline='').write(''.join(out))
