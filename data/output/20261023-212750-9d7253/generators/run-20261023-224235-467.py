
code = r'''

# ------------------------------------------------------------------------------------------------ helpers
SP_TOP = ytop(4)             # top of the brick course on layers 2-4 (y = -40)
NAC_TOP = ytop(7)            # top of the nacelle brick course on layers 5-7 (y = -64)
FACE_YAW = {(0, 0, -1): 0, (1, 0, 0): -90, (0, 0, 1): 180, (-1, 0, 0): 90}


def side_stud(sec, id, colour, face, cx, cz, top, purpose=None):
    """30414 with its four side studs facing `face`; (cx, cz) is the brick centre in LDU."""
    return sec.add(id, '30414', colour, [cx, top, cz], Ry(FACE_YAW[tuple(face)]), purpose or f'side studs face {face}')


def deck_colour(cx, z):
    if cx in (-1, 0) and 7 <= z <= 17:
        return BK
    if cx in (-3, 2) and -8 <= z <= 6:
        return YL
    if cx in (-4, 3) and z >= 8:
        return BK
    return DG


def body():
    s = Section('kestrel4-body.ldr', 'Hull: Technic spine, wall bricks, side-stud mounts, deck, cockpit floor and interior')
    rng = random.Random(21)
    s.step()
    for k in range(6):
        z0 = -8 + 4 * k
        zc = (z0 + 2) * 20
        for cx in (-1, 0):
            s.add(f'spine-{k}-{cx}', '3701', BK, [cx * 20 + 10, SP_TOP, zc], Ry(90), 'Technic spine brick, holes across the hull')
        for dz in (-20, 0, 20):
            col = YL if WIN[0] <= z0 <= WIN[1] else BK
            s.add(f'pin-{k}-{dz}', '4459', col, [0, SP_TOP + 10, zc + dz], None, 'Friction pin locking the spine pair')
    s.step()
    reserved = set()
    for cx0, face in ((3, (1, 0, 0)), (-4, (-1, 0, 0))):
        for z0 in (-8, -4):
            side_stud(s, f'flank-mount-{cx0}-{z0}', DG, face, cx0 * 20 + 10, (z0 + 2) * 20, SP_TOP, 'Flank panel mount')
            reserved |= {(cx0, z) for z in range(z0, z0 + 4)}
    for cx0 in (-4, 0):
        side_stud(s, f'aft-mount-{cx0}', DG, (0, 0, 1), (cx0 + 2) * 20, 17 * 20 + 10, SP_TOP, 'Aft cap mount')
        reserved |= {(cx0 + i, 17) for i in range(4)}
    walls = {}
    for z in range(-8, 18):
        for cx in range(-4, 4):
            if cx in (-1, 0) and z <= 15:
                continue
            if cx not in (-1, 0) and WIN[0] <= z <= WIN[1]:
                continue
            if (cx, z) in reserved:
                continue
            walls[(cx, z)] = DG
    pack(s, walls, BRICK, SP_TOP, rng, 'z', maxlen=6, p2=0.3, prefix='wall', purpose='Wall brick course')
    s.step()
    deck = {(cx, z): DG for (cx, z) in FUS if z >= -8}
    pack(s, deck, PLATE, ytop(5), rng, 'z', maxlen=8, p2=0.35, prefix='deck', purpose='Deck plate layer')
    s.step()
    tiles = {(cx, z): deck_colour(cx, z) for (cx, z) in FUS
             if z >= -8 and not (-2 <= cx <= 1 and -7 <= z <= -1)}
    pack(s, tiles, TILE, ytop(6), rng, 'x', maxlen=4, p2=0.25, prefix='dt', purpose='Deck tile')
    t = ytop(6)
    for side, (a, b) in (('s', (1, 2)), ('p', (-2, -1))):
        s.rect('3069b', LG, a, b, -7, -5, t, 'sill', 'Cabin sill')
        s.rect('3069b', LG, a, b, -4, -2, t, 'side', 'Cabin side')
    s.rect('2431', YL, -2, 2, -5, -4, t, 'console', 'Instrument console')
    s.rect('3068b', BK, -1, 1, -4, -2, t, 'seat', 'Seat')
    s.rect('87079', BK, -2, 2, -2, 0, t, 'aft', 'Cabin aft')
    s.add('canopy', '30384', GLASS, [0, ytop(5), -90], None, 'Rounded canopy on the four floor studs')
    return s


def wing(side):
    sx = 1 if side == 's' else -1
    f = (lambda c: c) if sx == 1 else (lambda c: (-1 - c[0], c[1]))
    s = Section(f'kestrel4-wing-{side}.ldr', f'{side} wing: tiled top layer, yellow leading edge, cannon mount')
    rng = random.Random(31 if sx == 1 else 32)
    top = wing_cells(2)
    cannon = (9, 11)
    cells = {}
    for c in top:
        if c == cannon:
            continue
        lead = (c[0], c[1] - 1) not in top
        cells[f(c)] = YL if lead else BK if c[1] == 17 else DG
    s.step()
    pack(s, cells, TILE, ytop(2), rng, 'x', maxlen=4, p2=0.3, prefix='wt', purpose='Wing top tile')
    s.step()
    cx, z = f(cannon)
    s.rect('3024', DG, cx, cx + 1, z, z + 1, ytop(2), 'cm', 'Plate under cannon mount')
    s.step()
    s.add('cannon-mount', '87087', DG, [cx * 20 + 10, ytop(5), z * 20 + 10], None, 'Side stud faces forward for the cannon')
    return s


def nacelle(side):
    sx = 1 if side == 's' else -1
    f = (lambda c: c) if sx == 1 else (lambda c: (-1 - c[0], c[1]))
    s = Section(f'kestrel4-nacelle-{side}.ldr', f'{side} engine nacelle: plate base, brick course with side studs, tiles, fin')
    rng = random.Random(41 if sx == 1 else 42)
    for layer in (2, 3, 4):
        s.step()
        pack(s, {f(c): DG for c in NAC}, PLATE, ytop(layer), rng, 'x' if layer % 2 else 'z', maxlen=6, p2=0.3,
             prefix=f'np{layer}', purpose='Nacelle plate layer')
    s.step()
    bx = 120 * sx
    side_stud(s, 'front-mount', DG, (0, 0, -1), bx, 150, NAC_TOP, 'Intake mount')
    side_stud(s, 'rear-mount', DG, (0, 0, 1), bx, 350, NAC_TOP, 'Nozzle mount')
    for i, z0 in enumerate((9, 13)):
        side_stud(s, f'pod-mount-{i}', DG, (sx, 0, 0), 150 * sx, (z0 + 2) * 20, NAC_TOP, 'Outer panel mount')
    res = {(c[0], 7) for c in NAC} | {(c[0], 17) for c in NAC} | {(7, z) for z in range(9, 17)}
    cells = {f(c): DG for c in NAC if c not in res}
    pack(s, cells, BRICK, NAC_TOP, rng, 'z', maxlen=4, p2=0.3, prefix='nb', purpose='Nacelle brick course')
    s.step()
    fin = {(6, z) for z in range(10, 17)}
    tiles = {}
    for c in NAC:
        if c in fin:
            continue
        col = YL if c[0] in (5, 6) and 9 <= c[1] <= 15 else BK if c[1] >= 16 else DG
        tiles[f(c)] = col
    pack(s, tiles, TILE, ytop(8), rng, 'z', maxlen=4, p2=0.25, prefix='nt', purpose='Nacelle top tile')
    pack(s, {f(c): DG for c in fin}, PLATE, ytop(8), rng, 'z', maxlen=4, p2=0, prefix='fb', purpose='Fin base plate')
    for j in range(5):
        s.step()
        z0 = 10 + j
        base = 9 + 3 * j
        col = YL if j == 2 else DG
        pack(s, {f((6, z)): col for z in range(z0, 17)}, BRICK, ytop(base + 2), rng, 'z', maxlen=4, p2=0,
             prefix=f'fin{j}', purpose='Swept fin course')
        cx, z = f((6, z0))
        s.add(f'fin-slope-{j}', '54200', DG if j != 2 else YL, [cx * 20 + 10, ytop(base + 2), z * 20 + 10], None, 'Leading-edge slope')
    s.step()
    s.rect('63864', YL, *(lambda c: (c[0], c[0] + 1))(f((6, 14))), 14, 17, ytop(24), 'fcap', 'Fin cap')
    return s


FLANK_R = {'s': orient(up=(1, 0, 0), along=(0, 0, 1)), 'p': orient(up=(-1, 0, 0), along=(0, 0, 1))}
FWD_R = orient(up=(0, 0, -1), along=(1, 0, 0))
AFT_R = orient(up=(0, 0, 1), along=(1, 0, 0))


def flank(side):
    sx = 1 if side == 's' else -1
    s = Section(f'kestrel4-flank-{side}.ldr', f'{side} flank panel built flat and turned onto side studs')
    up = 10 * sx
    s.step().add('base', '3034', DG, [0, -8, 0], None, 'Two-row base plate on the side studs')
    s.step()
    s.add('stripe', '4162', YL, [0, -16, up], None, 'Yellow stripe')
    s.add('lower-a', '2431', BK, [-40, -16, -up], None, 'Lower tile')
    s.add('lower-b', '2431', DG, [40, -16, -up], None, 'Lower tile')
    return s


def pod_panel(side):
    s = Section(f'kestrel4-pod-panel-{side}.ldr', f'{side} nacelle outer stripe')
    s.step().add('base', '3460', DG, [0, -8, 0], None, 'One-row base on side studs')
    s.step().add('stripe', '4162', YL, [0, -16, 0], None, 'Stripe')
    return s


def intake():
    s = Section('kestrel4-intake.ldr', 'Intake ring, hub and spinner built along their own axis')
    s.step().add('ring', '60474', BK, [0, 0, 0], None, 'Round 4x4 on four forward studs')
    s.step().add('hub', '3941', DG, [0, -24, 0], None, 'Hub')
    s.step().add('spinner', '98100', YL, [0, -48, 0], None, 'Spinner')
    return s


def nozzle():
    s = Section('kestrel4-exhaust.ldr', 'Exhaust nozzle: ring, jumper, bell and glowing core')
    s.step().add('ring', '60474', BK, [0, 0, 0], None, 'Ring on four aft studs')
    s.step().add('jumper', '87580', BK, [0, -8, 0], None, 'Centre stud')
    s.step().add('bell', '3960', DG, [0, -24, 0], None, 'Bell')
    s.step().add('core', '4740', GLOW, [0, -32, 0], None, 'Glowing core')
    return s


def aft_cap():
    s = Section('kestrel4-aft-cap.ldr', 'Aft cap: dark panel with grille and glowing vents')
    s.step().add('panel', '3020', BK, [0, 0, 0], None, 'On aft-facing studs')
    s.step()
    s.add('vent-a', '98138', GLOW, [30, -8, -10], None, 'Vent')
    s.add('vent-b', '98138', GLOW, [-30, -8, -10], None, 'Vent')
    s.add('grille', '2412b', LG, [0, -8, -10], None, 'Grille')
    s.add('lower', '2431', DG, [0, -8, 10], None, 'Lower tile')
    return s


def cannon():
    s = Section('kestrel4-cannon.ldr', 'Wing-root cannon stacked along its own axis')
    for i, (ref, col, y) in enumerate((('85861', BK, 0), ('3062b', DG, -24), ('85861', YL, -32),
                                       ('3062b', DG, -56), ('98138', BK, -64))):
        s.step().add(f'barrel-{i}', ref, col, [0, y, 0])
    return s


def build():
    mods = [keel(), nose(), body(), wing('s'), wing('p'), nacelle('s'), nacelle('p'), flank('s'), flank('p'),
            pod_panel('s'), pod_panel('p'), intake(), nozzle(), aft_cap(), cannon()]
    root = Section('kestrel4.ldr', 'Kestrel Mk IV strike skiff, floating pose')
    for name in ('keel', 'nose', 'body'):
        root.step().add(name, f'kestrel4-{name}.ldr', 16, [0, 0, 0])
    root.step()
    for side in 'sp':
        root.add(f'wing-{side}', f'kestrel4-wing-{side}.ldr', 16, [0, 0, 0])
        root.add(f'nacelle-{side}', f'kestrel4-nacelle-{side}.ldr', 16, [0, 0, 0])
    root.step()
    for side, sx in (('s', 1), ('p', -1)):
        root.add(f'flank-{side}', f'kestrel4-flank-{side}.ldr', 16,
                 seat(FLANK_R[side], [-70, 0, 10 * sx], [80 * sx, SP_TOP + 10, -150]), FLANK_R[side])
        root.add(f'pod-panel-{side}', f'kestrel4-pod-panel-{side}.ldr', 16,
                 seat(FLANK_R[side], [-70, 0, 0], [160 * sx, NAC_TOP + 10, 190]), FLANK_R[side])
    root.step()
    for side, sx in (('s', 1), ('p', -1)):
        bx = 120 * sx
        root.add(f'intake-{side}', 'kestrel4-intake.ldr', 16, seat(FWD_R, [10, 8, 10], [bx + 10, NAC_TOP + 10, 140]), FWD_R)
        root.add(f'exhaust-{side}', 'kestrel4-exhaust.ldr', 16, seat(AFT_R, [10, 8, -10], [bx + 10, NAC_TOP + 10, 360]), AFT_R)
        root.add(f'cannon-{side}', 'kestrel4-cannon.ldr', 16, seat(FWD_R, [0, 8, 0], [190 * sx, ytop(5) + 10, 220]), FWD_R)
        root.add(f'aft-cap-{side}', 'kestrel4-aft-cap.ldr', 16,
                 seat(AFT_R, [10, 8, -10], [40 * sx + 10, SP_TOP + 10, 360]), AFT_R)
    return dict(version=1, author=AUTHOR, sections=[root.plan()] + [m.plan() for m in mods])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=HERE / 'kestrel4.plan.json')
    a = ap.parse_args()
    plan = build()
    a.output.write_text(json.dumps(plan, indent=1) + '\n')
    n = sum(len(st) for sec in plan['sections'] for st in sec['steps'])
    print(a.output, 'placements incl. module refs:', n)


if __name__ == '__main__':
    main()
'''
open('output/kestrel4/generate.py','a').write(code)
