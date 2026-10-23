import pathlib
p=pathlib.Path('output/nightfang/generate.py'); s=p.read_text()
s=s.replace("body.add('98282', Y, s, 62, z, yaw=-90 * s)","body.add('98282', K, s, 62, z, yaw=-90 * s)")
# tail deck: lanes as plates, inner 4-wide: plates (louvre area) then tiles
old="slab(body, -3, 2, 6, 10, 70, Y)                      # tail deck (studs for fins/wing)"
new='''for s in (-1, 1):                                    # studded shoulder rails carry the fins
    line(body, s * 2.5 - .5, 2, 10, 70, Y, axis='z', plate=True)
slab(body, -2, 2, 4, 4, 70, Y)                       # louvre bed (studs)
tiles_z(body, -2, 6, 6, 70, Y)                       # smooth engine cover
tiles_z(body, 0, 6, 6, 70, Y)'''
assert old in s; s=s.replace(old,new)
# fins: replace
old=s[s.index("for s in (-1, 1):\n    top.add('3010', Y, s * 2.5, 94, 10, yaw=90)"):s.index("top.add('3034', K, 0, 126, 11, id='wing')")]
new='''for s in (-1, 1):
    # swept shark-fin haunch: 1x6 + 1x4 base, 33deg slope rising into a 1x4 wing mount
    top.add('3009', Y, s * 2.5, 94, 5, yaw=90)          # z 2..8
    top.add('3010', Y, s * 2.5, 94, 10, yaw=90)         # z 8..12
    top.add('4286', Y, s * 2.5, 118, 7.5)               # slope rising to the rear (checked in render)
    top.add('3010', Y, s * 2.5, 118, 10, yaw=90)
'''
s=s.replace(old,new)
s=s.replace("    top.add('3039', K, x, 94, 0.5)","    top.add('3039', K, x, 94, 0.5)",1)
p.write_text(s)
import sys; sys.path.insert(0,'.')
from ldraw_tools.common import get_parts
g=get_parts().geometry('3009'); print(g.bounds.min,g.bounds.max)