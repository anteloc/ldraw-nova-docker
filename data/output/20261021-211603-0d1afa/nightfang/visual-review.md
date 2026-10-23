# Nightfang visual review

Images opened: r2/home, r2/right, r2/front, r2/back; r3/home, r3/right; r4/left, top, bottom; final-views/home, front.

Findings and fixes
- v1 was a flat slab; added nose curved slopes, bubble canopy (2437 x2, trans-black), black roof tiles, seats, wheel.
- Tail was boxy with a studded deck -> rebuilt as swept fin haunches (1x6/1x4 bricks + 33deg slope + 1x4 wing mount),
  tiled engine cover, louvre grilles; wheel arches (98282) switched to black for contrast.
- Splitter 3795 was oriented along Z (stuck out forward) -> rotated across the nose; diffuser added at the rear.
- Steering stand floated 8 LDU high (h=78) -> lowered to h=70 (confirmed by connector bounds).
- Nose grille: two 87087 front-stud bricks + 2412b grille tile between headlights.

Remaining limitations
- Overall shape is long/low and rather wide-bodied for the wheels; real Le Mans cars have more curved bodywork than the stud grid allows.
- Cockpit interior is only visible through the tinted canopy; seats are plate+slope, not 4079 (too tall for the canopy).
- Lamps (6141) are seated in recessed 4070 studs; the connection checker has no evidence for those joints (5 optimistic groups),
  nor for wheel pins (4 wheel-pair groups). Not claimed as verified.
- physical_validity remains not_proven; part/colour availability not verified.
