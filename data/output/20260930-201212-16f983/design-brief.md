# Fiamma V8: design brief (medium Technic hypercar, ~900 parts)

## Subject and story
An orange-and-black mid-engine road hypercar. The cab sits forward. Behind the cabin is a **longitudinal V8, visible through a slatted
black engine cover**, and the V8 is driven from the rear wheels through a working 2-speed gearbox. Stance: low, wide, planted.
The design aims for a *clean wedge with one exposed machine*: quiet orange flanks, and every mechanical feature concentrated
in the rear third.

## Silhouette (car frame: X across, -Z forward, Y=0 road, Z=0 front axle centre)
- **Wedge in side view:** the nose is only ~110 LDU high at the tip (Z≈-250). The bonnet rises to the windscreen base
  (Z≈+60, Y≈-170). A steeply raked screen leads to the roof peak (Y≈-270, Z≈200-330). The engine cover then falls
  gently to the tail (Y≈-190 at Z≈950).
- **Raised rear wing** on two swan-neck supports: blade at Y≈-300, Z≈900-960, spanning about 23 of the 29 studs of width.
- **Mass split:** front overhang 250, wheelbase 740 (37 studs), rear overhang 230 → length ≈1220 LDU (61 studs, ~49 cm).
  Width ≈580 LDU (29 studs) over the tyre track of 459 (tyre centres). The body is about 270 high, or about 300 at the wing.
- **Wheels:** 15038 rims + 44771 tyres (Ø172 × 88 LDU). The large, nearly flush wheels fill their arches; the front arches are
  cut high and the rear arches are wider.

## Palette roles (LDraw codes)
| Role | Colour | Where |
|---|---|---|
| Dominant body | Orange 25 | nose, flanks, doors, rear haunches |
| Secondary / graphic | Black 0 | roof and screen frame, sills, splitter, diffuser, wing, engine-cover slats, tyres |
| Structure / mechanics | Dark bluish grey 72 | frame, suspension, gearbox housing |
| Functional hardware | Light bluish grey 71 / tan / blue (standard pin & axle colours) | pins and axles (mostly hidden) |
| Metal accent | Flat silver 179 | rims, exhaust tips |
| Focal accent | V8 in light bluish grey with red 4 cylinder-head accents | engine only, seen through the slats |
| Lamps | Trans-clear 47 (front), trans-red 36 (rear) | slim light bars |

Colours are chosen as palette roles. Retail part/colour availability is **not** verified.

## Focal hierarchy
1. **Primary:** the V8 under the slatted black engine cover behind the cabin. The engine is raised 2 studs above the donor
   position so the pistons read clearly through the slats.
2. **Supporting 1:** butterfly doors. They hinge at the A-pillar and swing up and forward, and they are shown in a raised pose
   in one review render.
3. **Supporting 2:** the raised rear wing and a black diffuser with twin centre exhausts.
- **Small accents:** slim light bars, an orange-rimmed side intake behind each door, and a HOG knob on the bonnet.

## Detail vocabulary and quiet surfaces
- **Vocabulary:** black-orange split along the sill line; horizontal slats; triangular intake openings; flush panels.
- **Quiet surfaces:** bonnet top, door skins and front wings are kept as large smooth orange panels. Surfaces are left
  without stickers.

## Functions (requested scope: all)
- Independent suspension on all four wheels, adapted from 42039, with library shock absorbers. The donor's raw spring
  meshes are replaced.
- Rack-and-pinion steering. It is driven by a HOG knob on the bonnet **and** a cockpit steering wheel.
- Rear differential with CV half-shafts.
- 2-speed gearbox: a driving ring + clutch gears (16T/16T and 20T/12T, 2-stud shaft spacing, 42112 pattern), in-line between
  the differential pinion and the engine crank, selected by a lever on the centre console.
- V8 piston engine, driven from the rear wheels through the gearbox.
- Two butterfly doors and a rear wing.
- **Analytical mechanism verification is deferred:** motion is described as intended, not tested.

## Physical subassemblies and build order
M1 frame → M2 rear axle + diff → M3 gearbox + shift linkage → M4 V8 → M5 front axle → M6 steering (rack, column, HOG,
wheel) → M7 cockpit (2 seats, dashboard, console lever) → M12 wheels → M9 body panels / M10 front & rear ends → M8 doors →
M11 wing. Contracts: `modules.json`; master dimensions: `layout.json`.

## What should make it attractive
- A readable wedge silhouette at thumbnail size.
- A strict three-colour discipline, with orange dominant.
- One exposed, well-lit machine in the rear.
- Big wheels filling their arches.
- Contrast between quiet panels and the concentrated mechanical detail.

Part count is **not** a quality goal.

## Reuse and originality
- **Donors (credited, extraction manifests kept):**
  - 42039 (front axle, steering rack, rear axle/diff, V8 motor, seat), used as mechanical donors.
  - 42112 gearshift, used as the gearbox pattern.
  - 42093 spoiler, used as the wing blade pattern.
- **Original work:**
  - Frame layout (tunnel, raised engine mounts, door hinge and body mounts).
  - The gearbox placement and shift linkage.
  - HOG plus steering-wheel input.
  - All bodywork, doors, the wing supports and the colour scheme.
