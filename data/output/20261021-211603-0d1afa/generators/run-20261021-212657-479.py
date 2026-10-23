import re,pathlib
p=pathlib.Path('output/nightfang/generate.py'); s=p.read_text()
s=s.replace("ch.add('3795', K, 0, 22, -11, yaw=90, id='splitter-core')",
 "ch.add('3795', K, 0, 22, -11, id='splitter')\nch.add('3795', K, 0, 22, 11, id='diffuser')")
extra='''
# -------------------------------------------------------------- nose slopes, canopy, interior, tail, wing
top = Module('nightfang-top', 'Nose slopes, glazing, seats, engine cover, fins and wing')
for x in (-2, 0, 2):
    top.add('15068', Y, x, 54, -11)                      # curved nose slopes (high end checked in render)
# sill plates carrying the glazing's lower edges
for z in (-3.5, 1.5):
    top.add('3710', K, 0, 70, z)
top.add('2437', TK, 0, 102, -2.5, id='windscreen')
top.add('2437', TK, 0, 102, 0.5, yaw=180, id='rear-window')
for z in (-2, 0):
    top.add('87079', K, 0, 110, z)                       # roof tiles on the glazing's top studs
# bucket seats (plate + 45deg slope back) and wheel
for x in (-1, 1):
    top.add('3022', K, x, 70, 0)
    top.add('3039', K, x, 94, 0.5)
top.add('3829c01', K, -1, 78, -2.5, id='wheel')
# engine cover louvres and twin fins carrying the wing
for z in (3.5, 4.5):
    for x in (-1, 1):
        top.add('2412b', K, x, 78, z, yaw=0)
for s in (-1, 1):
    top.add('3010', Y, s * 2.5, 94, 10, yaw=90)
    top.add('3040b', Y, s * 2.5, 118, 9.5)
    top.add('3004', Y, s * 2.5, 118, 11, yaw=90)
top.add('3034', K, 0, 126, 11, id='wing')
top.add('4162', Y, 0, 134, 10.5)
top.add('4162', Y, 0, 134, 11.5)
for s in (-1, 1):
    for z in (10.5, 11.5):
        top.add('87087', K, s * 3.5, 118, z, yaw=-90 if s > 0 else 90)
    skin(top, s, 10, 2, 118, K, x_face=80)
car.add(top, Y, id='top')
'''
s=s.replace("plan = car.plan()", extra+"\nplan = car.plan()")
p.write_text(s)