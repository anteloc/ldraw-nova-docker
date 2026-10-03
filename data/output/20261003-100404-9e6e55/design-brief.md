# The Garden Cottage — design brief

## Subject / story
A large, cosy country cottage on a green lawn, with a small **kitchen garden** (raised
vegetable beds with growing crops) at the back, a picket fence, a well, a tree and a
stone path. The mood is a lived-in English country home in summer: warm walls, a deep
red roof, and a busy little vegetable patch.

## Silhouette (recognisable at thumbnail size)
- **Two main masses:** a tall two-storey main hall (left) with a hipped roof and a
  tall stone chimney, and a lower one-storey wing (right) with its own roof. The
  height step between them is the primary silhouette feature.
- **A clear base:** the whole scene sits on a 32×32 green lawn baseplate; the house
  occupies the front, the garden patch the back.
- The chimney breaks the roofline so the cottage reads as a home, not a barn.

## Focal hierarchy
1. **Primary:** the cottage front — tall grey stone chimney, dark-red hipped roof,
   cream walls, a wooden front door with a small porch, and a flower box under a window.
2. **Supporting A:** the vegetable field — four raised wooden beds with distinct crops
   (lettuce, cabbage, carrots, tomatoes), a scarecrow, and a harvest basket.
3. **Supporting B:** the setting — the stone path, the well, the tree and the low
   white picket fence framing the garden.

## Dimensions (studs / LDU), scene on 32×32 baseplate (X ±320, Z ±320)
- House footprint: ~14 wide (X −140…+140) × 8 deep (Z −90…+90), front at Z −90.
  - Main hall: 8 wide × 8 deep, two storeys (walls 4 courses = 96 LDU) + hipped roof.
  - Wing: 6 wide × 8 deep, one storey (walls 2 courses = 48 LDU) + lower hipped roof.
- Garden field: ~11 wide (X −110…+110) × 5 deep (Z +90…+190), behind the house.
  - Four raised beds 6×4, a central path, a picket fence on the 3 far sides + a gate.
- Tree at front-left (X −260, Z −220); well at front-right (X +260, Z −160).
- Stone path from the front door to the front edge (Z −90…−320) and to the field.

## Palette roles (role → LDraw colour)
- **Walls/body:** Tan (19) — dominant, warm.
- **Trim / window frames / door surround / fence:** White (15).
- **Stone (base course, sills, chimney, path, well, patio):** Light Bluish Grey (71).
- **Roof + ridge:** Dark Red (320).
- **Wood (door, raised-bed sides, scarecrow, well roof):** Reddish Brown (70).
- **Soil:** Brown (6).
- **Glass:** Trans Clear (47).
- **Vegetation / crops:** Dark Green (288), Green (2), Bright Green (394) for tops.
- **Crop accents:** Red (1) tomatoes, Orange (233) carrots/peppers, Bright Pink (29) flowers.
- **Metal / smoke:** Black (0) optional.
Composition: keep tan + dark-red dominant; green only in the garden and the lawn;
white trim repeated on windows, fence and door so the eye tracks the openings.

## Detail vocabulary (consistent motifs)
- White-framed windows with a stone sill and, on the ground floor, a white lintel.
- Corner quoins (white) on the main hall for a crafted look.
- A raised wooden bed frame (reddish-brown) with dark soil inside, repeated 4×.
- Low white picket fence with a small gate.
Flower box (dark pink) under one front window ties the house to the garden.

## Quiet surfaces vs. detail
- Quiet: the large tan wall faces (few, evenly spaced windows), the plain red roof,
  the open lawn.
- Detailed: the entrance (door + porch + flower box + step), the chimney, and the
  vegetable field (the busiest zone, by design, at the back).

## Physical sub-assemblies & build order
1. `cottage-ground` — baseplate, lawn, stone path, front patio.
2. `cottage-house` — hall + wing walls, quoins, stone base, windows, door, porch,
   flower box, hipped roofs, chimney.
3. `cottage-garden` — four raised beds + crops, harvest basket, scarecrow, water barrel.
4. `cottage-fence` — picket fence + gate around the field.
5. `cottage-land` — tree, well, bushes, flowers.
6. `cottage-scene` (main) — places 1–5 in the world, one baseplate colour scheme.

## What makes this attractive
The two-storey / one-storey height step, the tall stone chimney and deep red hip read
as a genuine cottage instantly; the contrasting white trim and stone base give crafted
edges; and the busy little vegetable field at the back — with clearly different crops,
a scarecrow and a harvest basket — tells the "growing vegetables" story the brief asks
for, without cluttering the quiet front.

## Sources (Jev discovery, viewed before use)
- 31038-1 cottage (tan stone, deep red hip, chimney) — proportion precedent.
- 4956-1 (white walls, red roof, front garden beds) — garden-bed + fence precedent.
- 40352 / 3315 garden submodels — carrot tops, picket fence, flower-stem crops.
All geometry is **rebuilt from official parts** for this scene; no OMR source is copied.
