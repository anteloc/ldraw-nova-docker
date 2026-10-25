
import re,os
os.makedirs('output/kestrel',exist_ok=True)
open('output/kestrel/brief.md','w').write("""# Kestrel-class strike skiff - brief
Style source: Naganata (black + dark-bluish-grey Technic-core fighter, yellow accent studs, paired wings, dish thrusters, side-stud skins).
Silhouette: long narrow nose, twin armoured engine nacelles with flat tiled decks, broad 6x12 wings, dorsal tail fins, rear dish thrusters.
Size ~ 584 x 480 x 140 LDU on a small display stand.
Palette: dark bluish grey 72 dominant, black 0 panels/thrusters/underside, yellow 14 stripes and intake accents, trans-light-blue 43 thruster cores, trans-black canopy.
Construction (after Halcyon SNOT approach): studs-up keel core -> 30414 side-stud course -> skins built upright and turned onto stud faces
(flanks, nacelle stripes, intakes, exhausts, aft cap, wing-root cannons) -> wings sandwiched on a root splice -> canopy -> stand.
Changes vs Halcyon example (reused construction skeleton, authorship noted): new palette, flat tiled armour decks with yellow stripes replacing curved nacelle tops,
black dish thruster/intake detail, dorsal round-stud row, yellow cannon rings.
Jev: not used; FTS/catalog only (parts chosen from the reference and the example).
""")
s=open('examples/snot/halcyon/generate.py').read()
s=s.replace("HULL, PANEL, FRAME, ACCENT, BLACK = 15, 71, 72, 321, 0","HULL, PANEL, FRAME, ACCENT, BLACK = 72, 0, 0, 14, 0")
s=s.replace("GLASS, GLOW = 40, 57","GLASS, GLOW = 40, 43")
s=s.replace("halcyon","kestrel").replace("Halcyon","Kestrel")
s=s.replace("AUTHOR = 'Kestrel generator (Claude Code, Claude Opus 5.5) for anteloc'","AUTHOR = 'Kestrel generator adapted from the Halcyon example construction, for carlos.antelo'")
i=s.index("    s.step()  # Rounded pod tops")
j=s.index("    return s\n",i)
new='''    s.step()  # Flat armoured nacelle decks: 4 x 2 tiles with a yellow centre stripe, plus black round studs
    for side, sx in SIDES:
        for i, z in enumerate(range(60, 220, 40)):
            col = ACCENT if i == 1 else HULL
            s.box(f'pod-deck-{side}-{i}', '87079', col, *xs(sx, 40, 120), z, z + 40, DECK)
'''
s=s[:i]+new+s[j:]
open('output/kestrel/generate.py','w').write(s)
