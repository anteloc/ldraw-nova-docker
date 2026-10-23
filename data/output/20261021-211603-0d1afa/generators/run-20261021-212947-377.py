import pathlib
p=pathlib.Path('output/nightfang/generate.py'); s=p.read_text()
s=s.replace("top.add('3829c01', K, -1, 78, -2.5, id='wheel')","top.add('3829c01', K, -1, 70, -2.5, id='wheel')")
s=s.replace("slab(ch, -2, -12, 4, 2, 46, K)          # nose core (outer cells hold hanging headlight bricks)",
"slab(ch, -2, -11, 4, 1, 46, K)          # nose core (front row of cells holds hanging brick/grille studs)")
# clean skin helper hack
s=s.replace("        m.add(ref_long if k == 2 else ref_one, colour, 0, h_top - 10, 0)  # placeholder replaced below\n        m.steps[-1].pop()\n","")
s=s.replace("    lamps.add('6141', TO, s * 2.5, 54 - 10 + 0, 0, matrix=FWD)   # placeholder, positioned below\n    lamps.steps[-1].pop()\n","")
# nose grille: two front-stud 87087 + grille tile
s=s.replace("# bridge nose -> front fenders","""for x in (-.5, .5):
    body.add('87087', Y, x, 54, -11.5)                                     # front stud, hangs under nose plate
# bridge nose -> front fenders""")
s=s.replace("car.add(sk, Y, id='skins')","""sk.steps[-1].append(dict(id='nose-grille', ref='2412b.dat', colour=K,
                         at=[0, -(54 - 10), 20 * -11.5 - 20 + 0], matrix=FWD))
car.add(sk, Y, id='skins')""")
p.write_text(s)