
p='output/kestrel4/generate.py'
s=open(p).read()
a=s.index("    for z0, z1, n in ((-16")
b=s.index("    # step bodies")
s=s[:a]+s[b:]
open(p,'w').write(s)
print(s[a-300:a+200])
