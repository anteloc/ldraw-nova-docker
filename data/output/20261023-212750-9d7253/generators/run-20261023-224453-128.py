
p='output/kestrel4/generate.py'
s=open(p).read()
def rep(a,b,cnt=1):
    global s
    assert s.count(a)>=1,(a)
    s=s.replace(a,b,cnt)
rep("return 8 + (z - 3) // 2          # exclusive outer bound at row z (z >= 5)","return 8 + (2 * (z - 3)) // 3     # exclusive outer bound at row z (z >= 5)")
rep("w1 = wing_cells(1)","w1 = wing_cells(0)")
# wing function
a=s.index("def wing(side):"); b=s.index("def nacelle(side):")
newwing='''def wing(side):
    sx = 1 if side == 's' else -1
    f = (lambda c: c) if sx == 1 else (lambda c: (-1 - c[0], c[1]))
    s = Section(f'kestrel4-wing-{side}.ldr', f'{side} wing: tiled top layer, raised inboard deck, yellow leading edge, cannon mount')
    rng = random.Random(31 if sx == 1 else 32)
    T0 = wing_cells(0)
    U = {c for c in T0 if c[1] >= 10 and c[0] < wing_e(c[1]) - 4}
    cannon = CANNON_CELL
    tiles = {}
    for c in T0 - U - {cannon}:
        lead = (c[0], c[1] - 1) not in T0
        second = (c[0], c[1] - 2) not in T0
        tiles[f(c)] = YL if lead else BK if (c[1] >= 16 or second) else DG
    s.step()
    pack(s, {f(c): DG for c in U | {cannon}}, PLATE, ytop(2), rng, 'x', maxlen=4, p2=0.3, prefix='wu', purpose='Wing inboard deck plate')
    pack(s, tiles, TILE, ytop(2), rng, 'x', maxlen=4, p2=0.3, prefix='wt', purpose='Wing top tile')
    s.step()
    ut = {f(c): (YL if (c[0], c[1] - 1) not in U else BK if c[1] == 17 else DG) for c in U}
    pack(s, ut, TILE, ytop(3), rng, 'z', maxlen=4, p2=0.3, prefix='wd', purpose='Raised wing deck tile')
    cx, z = f(cannon)
    s.add('cannon-mount', '87087', DG, [cx * 20 + 10, ytop(5), z * 20 + 10], None, 'Side stud faces forward for the cannon')
    return s


'''
s=s[:a]+newwing+s[b:]
rep("WIN = (0, 6)","CANNON_CELL = (9, 6)\nWIN = (0, 6)")
rep("[190 * sx, ytop(5) + 10, 220]","[190 * sx, ytop(5) + 10, 120]")
# fin 4 courses
rep("    for j in range(5):\n        s.step()\n        z0 = 10 + j","    for j in range(4):\n        s.step()\n        z0 = 10 + j")
rep("    s.rect('63864', YL, *(lambda c: (c[0], c[0] + 1))(f((6, 14))), 14, 17, ytop(24), 'fcap', 'Fin cap')","    s.rect('2431', YL, *(lambda c: (c[0], c[0] + 1))(f((6, 13))), 13, 17, ytop(21), 'fcap', 'Fin cap')")
# body: ridge + grilles
rep("""    tiles = {(cx, z): deck_colour(cx, z) for (cx, z) in FUS
             if z >= -8 and not (-2 <= cx <= 1 and -7 <= z <= -1)}
    pack(s, tiles, TILE, ytop(6), rng, 'x', maxlen=4, p2=0.25, prefix='dt', purpose='Deck tile')""","""    ridge = {(cx, z): BK for cx in (-1, 0) for z in range(7, 16)}
    grilles = [(a, a + 2, z) for z in (10, 12, 14) for a in (1, -3)]
    gcells = {(x, z) for a, b, z in grilles for x in range(a, b)}
    tiles = {(cx, z): deck_colour(cx, z) for (cx, z) in FUS
             if z >= -8 and not (-2 <= cx <= 1 and -7 <= z <= -1) and (cx, z) not in ridge and (cx, z) not in gcells}
    pack(s, tiles, TILE, ytop(6), rng, 'x', maxlen=4, p2=0.25, prefix='dt', purpose='Deck tile')
    for a, b, z in grilles:
        s.rect('2412b', LG, a, b, z, z + 1, ytop(6), 'grille', 'Deck grille')
    pack(s, ridge, PLATE, ytop(6), rng, 'z', maxlen=8, p2=0, prefix='rp', purpose='Ridge base plate')
    for cx in (-1, 0):
        s.add(f'ridge-slope-{cx}', '54200', YL, [cx * 20 + 10, ytop(6), 7 * 20 + 10], None, 'Ridge ramp')
    s.step()
    for k, z0 in enumerate((8, 12)):
        zc = (z0 + 2) * 20
        for cx in (-1, 0):
            s.add(f'ridge-{k}-{cx}', '3701', BK, [cx * 20 + 10, ytop(9), zc], Ry(90), 'Dorsal Technic ridge brick')
        for dz in (-20, 0, 20):
            s.add(f'ridge-pin-{k}-{dz}', '4459', YL, [0, ytop(9) + 10, zc + dz], None, 'Ridge pin')
        s.rect('87079', YL if k == 0 else DG, -1, 1, z0, z0 + 4, ytop(10), 'ridge-tile', 'Ridge cap tile')
    s.step()""")
# belly
rep("def build():","""def belly():
    s = Section('kestrel4-belly.ldr', 'Ventral Technic keel hanging under the hull: studs up into the keel underside')
    rng = random.Random(51)
    s.step()
    for k in range(4):
        z0 = -4 + 4 * k
        zc = (z0 + 2) * 20
        for cx in (-1, 0):
            s.add(f'bspine-{k}-{cx}', '3701', BK, [cx * 20 + 10, 0, zc], Ry(90), 'Ventral Technic brick')
        for dz in (-20, 0, 20):
            s.add(f'bpin-{k}-{dz}', '4459', YL, [0, 10, zc + dz], None, 'Ventral pin')
    caps = {(cx, z): BK for cx in (-2, 1) for z in list(range(-4, 0)) + list(range(8, 12))}
    pack(s, caps, BRICK, 0, rng, 'z', maxlen=4, p2=0, prefix='bw', purpose='Ventral end brick')
    s.step()
    under = {(cx, z): DG for cx in range(-2, 2) for z in range(-4, 12)}
    pack(s, under, PLATE, 24, rng, 'x', maxlen=6, p2=0.3, prefix='bu', purpose='Ventral plate layer')
    return s


def build():""")
rep("mods = [keel(), nose(), body(),","mods = [keel(), nose(), body(), belly(),")
rep("for name in ('keel', 'nose', 'body'):","for name in ('keel', 'nose', 'body', 'belly'):")
open(p,'w').write(s)
