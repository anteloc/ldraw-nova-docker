"""Nightfang: yellow/black Le Mans-style SNOT hypercar. Run from repo root:
   .venv/bin/python output/nightfang/generate.py
X across, -Z forward, h = LDU above road (top plane of the part origin; bodies hang below)."""
import json, sys, pathlib
sys.path.insert(0, '.')
from ldraw_tools.architecture import Module, slab, line, lengths, WIDE_PLATES
from ldraw_tools.vehicles import axle

Y, K, CL, TK, TO, TR, G, DG = 14, 0, 47, 40, 182, 36, 71, 72
L = 24
HALF = L // 2
FA, RA = -7, 6                      # axle stations (studs)

# proper rotations: local up -> world direction (verified below)
FWD = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]     # studs face -Z
BACK = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]    # studs face +Z
RIGHT = [[0, -1, 0], [0, 0, -1], [1, 0, 0]]  # studs face +X
LEFT = [[0, 1, 0], [0, 0, 1], [1, 0, 0]]     # studs face -X

def apply(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]
def det(m):
    return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1]) - m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
            + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
for n_, m_, w_ in [('FWD', FWD, [0, 0, -1]), ('BACK', BACK, [0, 0, 1]),
                   ('RIGHT', RIGHT, [1, 0, 0]), ('LEFT', LEFT, [-1, 0, 0])]:
    assert apply(m_, [0, -1, 0]) == w_, n_
    assert det(m_) == 1, n_

car = Module('nightfang', 'Nightfang Le Mans hypercar, front -Z, ground Y=0')

# -------------------------------------------------------------- helpers
def tiles_z(m, x0, z0, d, h, colour):
    """2-wide tile strip running along Z (x0 = lower x edge in studs)."""
    z = z0
    while d > 0:
        n = 4 if d >= 4 else 2
        m.add('87079' if n == 4 else '3068b', colour, x0 + 1, h, z + n / 2, yaw=90 if n == 4 else 0)
        z += n; d -= n

def skin(m, side, z0, n, h_top, colour, ref_long='3069b', ref_one='3070b', x_face=60):
    """Tiles standing on outward side-studs of 87087 bricks (stud centre 10 below brick top).
    side=+1 right, -1 left. z0, n in studs. Tile is 20 high, centred on the stud row."""
    mat = RIGHT if side > 0 else LEFT
    ox = side * (x_face + 8)
    cur = z0
    while n > 0:
        k = 2 if n >= 2 else 1
        p = dict(id=f'skin{m.serial}', ref=(ref_long if k == 2 else ref_one) + '.dat', colour=colour,
                 at=[ox, -(h_top - 10), 20 * (cur + k / 2)], matrix=mat)
        m.serial += 1
        m.steps[-1].append(p)
        cur += k; n -= k

def side_brick(m, side, x, z, h_top, colour, ref='87087', facing='out'):
    """Hanging side-stud brick; stud faces outward (+-X), up-stud engages the plate above."""
    m.add(ref, colour, x, h_top, z, yaw=-90 if side > 0 else 90)

# -------------------------------------------------------------- running gear
run = axle('touring', rim_colour=Y)
car.add(run, 0, z=FA, id='front-axle')
car.add(run, 0, z=RA, id='rear-axle')

# -------------------------------------------------------------- chassis
ch = Module('nightfang-chassis', 'Bonded 2-wide spine; plates/slabs sit in the wheel-free bays')
for h, runs in [(30, list(lengths(L))), (38, [2, *lengths(L - 2)])]:
    cur = -HALF
    for n in runs:
        ch.add(WIDE_PLATES[n], K, h=h, z=cur + n / 2, yaw=0 if n == 1 else 90)
        cur += n
# bays (studs): nose -12..-10 | front lane -10..-5 handled by fenders | mid -5..4 | tail 8..12
slab(ch, -2, -11, 4, 1, 46, K)          # nose core (front row of cells holds hanging brick/grille studs)
slab(ch, -3, -10, 6, 1, 46, K)          # nose-to-fender bridge
slab(ch, -2, -5, 4, 9, 46, K)           # cockpit floor core (lanes hold side bricks)
slab(ch, -2, 8, 4, 4, 46, K)            # tail core
# black splitter and diffuser plates hang under the spine (studs up into spine underside)
ch.add('3795', K, 0, 22, -11, id='splitter')
ch.add('3795', K, 0, 22, 11, id='diffuser')
car.add(ch, K, id='chassis')

# -------------------------------------------------------------- body
body = Module('nightfang-body', 'Yellow structure: fenders, nose, flank bricks and decks')
for z in (FA, RA):
    for s in (-1, 1):
        body.add('98282', K, s, 62, z, yaw=-90 * s)

# nose (z -12..-10): plate 54 over core; hanging headlight bricks in the outer cells
slab(body, -3, -12, 6, 2, 54, Y)
for s in (-1, 1):
    body.add('4070', K, s * 2.5, 54, -11.5, id=f'headlight-brick-{s}')      # stud faces forward
    side_brick(body, s, s * 2.5, -10.5, 54, Y)
for x in (-.5, .5):
    body.add('87087', Y, x, 54, -11.5)                                     # front stud, hangs under nose plate
# bridge nose -> front fenders (z -10..-9)
slab(body, -3, -10, 6, 1, 54, Y)
slab(body, -3, -10, 6, 1, 62, Y)
# mid bay: 4-wide plate stack on the core, lanes of side-stud bricks hanging from the deck
slab(body, -2, -5, 4, 9, 54, Y)
slab(body, -2, -5, 4, 9, 62, Y)
for s in (-1, 1):
    for i in range(9):
        side_brick(body, s, s * 2.5, -4.5 + i, 62, Y)
# tail bay
slab(body, -2, 8, 4, 4, 54, Y)
slab(body, -2, 8, 4, 4, 62, Y)
for s in (-1, 1):
    for i in range(3):
        side_brick(body, s, s * 2.5, 8.5 + i, 62, Y)
    body.add('4070', K, s * 2.5, 62, 11.5, yaw=180, id=f'tail-brick-{s}')   # stud faces rear
# deck (plates at 70 over fenders / tail, tiles on hood) -- hood z -10..-4, cockpit -4..2, tail 2..12
for x0 in (-3, -1, 1):
    tiles_z(body, x0, -10, 6, 70, K if x0 == -1 else Y)
for s in (-1, 1):
    # flank shoulders (outer lane) over the cockpit and fender zones
    slab(body, s * 2.5 - .5 if s > 0 else s * 2.5 - .5, -4, 1, 6, 70, Y)
for s in (-1, 1):                                    # studded shoulder rails carry the fins
    line(body, s * 2.5, 2, 10, 70, Y, axis='z', plate=True)
slab(body, -2, 2, 4, 4, 70, Y)                       # louvre bed (studs)
tiles_z(body, -2, 6, 6, 70, Y)                       # smooth engine cover
tiles_z(body, 0, 6, 6, 70, Y)
car.add(body, Y, id='body')

# -------------------------------------------------------------- skins (SNOT flanks)
sk = Module('nightfang-skins', 'Tile skins on outward side studs')
for s in (-1, 1):
    # door: yellow tiles z -5..-1 + black grille intake z -1..1 + yellow 1x1s
    skin(sk, s, -5, 4, 62, Y)
    p = dict(id=f'grille-{s}', ref='2412b.dat', colour=K,
             at=[s * 68, -(62 - 10), 20 * 0], matrix=RIGHT if s > 0 else LEFT)
    sk.steps[-1].append(p)
    skin(sk, s, 1, 3, 62, Y)
    skin(sk, s, 8, 4, 62, Y)       # tail lane
    skin(sk, s, -11, 1, 54, Y)     # nose lane
sk.steps[-1].append(dict(id='nose-grille', ref='2412b.dat', colour=K,
                         at=[0, -(54 - 10), -248], matrix=FWD))
car.add(sk, Y, id='skins')

# -------------------------------------------------------------- lamps (clear/orange front, red rear)
lamps = Module('nightfang-lamps', 'Round plates plugged into the 4070 recessed side studs')
for s in (-1, 1):
    lamps.steps[-1].append(dict(id=f'headlamp-{s}', ref='6141.dat', colour=47,
                                at=[s * 50, -(54 - 10), 20 * -11.5 - 14], matrix=FWD))
    lamps.steps[-1].append(dict(id=f'taillamp-{s}', ref='6141.dat', colour=TR,
                                at=[s * 50, -(62 - 10), 20 * 11.5 + 14], matrix=BACK))
car.add(lamps, TR, id='lamps')


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
top.add('3829c01', K, -1, 70, -2.5, id='wheel')
# engine cover louvres and twin fins carrying the wing
for z in (3.5, 4.5):
    for x in (-1, 1):
        top.add('2412b', K, x, 78, z, yaw=0)
for s in (-1, 1):
    # swept shark-fin haunch: 1x6 + 1x4 base, 33deg slope rising into a 1x4 wing mount
    top.add('3009', Y, s * 2.5, 94, 5, yaw=90)          # z 2..8
    top.add('3010', Y, s * 2.5, 94, 10, yaw=90)         # z 8..12
    top.add('4286', Y, s * 2.5, 118, 7.5)               # slope rising to the rear (checked in render)
    top.add('3010', Y, s * 2.5, 118, 10, yaw=90)
top.add('3034', K, 0, 126, 11, id='wing')
top.add('4162', Y, 0, 134, 10.5)
top.add('4162', Y, 0, 134, 11.5)
for s in (-1, 1):
    for z in (10.5, 11.5):
        top.add('87087', K, s * 3.5, 118, z, yaw=-90 if s > 0 else 90)
    skin(top, s, 10, 2, 118, K, x_face=80)
car.add(top, Y, id='top')

plan = car.plan()
plan['author'] = 'Claude (LDraw Nova agent) for carlos.antelo@gmail.com'
out = pathlib.Path('output/nightfang/nightfang.plan.json')
out.write_text(json.dumps(plan, indent=1))
print('wrote', out, sum(len(s) for sec in plan['sections'] for s in sec['steps']), 'placements in plan')
