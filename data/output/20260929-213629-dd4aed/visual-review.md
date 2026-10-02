# Bradbury Building — visual review

Reviewed against the [design brief](design-brief.md) and the supplied reference photograph
(Broadway and 3rd Street elevation). Geometry passing was the starting condition, not the
finish line; every change below came from opening an actual rendered image or reading a
contact report, and each was fixed in the generator and rebuilt.

## Images actually opened

| Round | Images opened |
|---|---|
| 1 | `review-1/` home, front, right, top |
| 2 | `review-2/` home, front · `review-storey/` home (single storey module) |
| 3 | `review-3/` home, left, back · `review-court/` home, top (cutaway) |
| Final | `review-final/` home, front, right, left, back, top · `review-court/` home, top |

## Round 1 — first whole-model views

| Observed in the image | Change made |
|---|---|
| Ground floor read as a thin band of narrow slots; the shopfronts did not register as shops. | Widened the ground-floor openings from 2 to 3 studs with single-stud stone piers, and made the top course of the ground storey's inner skin **white** so a continuous sign fascia shows above every shopfront. |
| Windows sat flush in the wall with no shadow line. | Added projecting sills: a 2x2 plate course one stud proud of the face under every opening, with a pale `2450` cut-corner sill on the chamfer. |
| Window heads were the same colour as the piers, so the arches disappeared. | Changed the `3659` Arch 1x4 heads to Dark Tan so the voussoirs read against the Tan piers. |
| The elevation had no vertical termination at the ends. | Added Reddish Brown corner pilasters at both ends of each street elevation. |

## Round 2 — module and interior review

| Observed | Change |
|---|---|
| The rendered storey module showed the light court ringed by a balustrade that stopped short of the corners. | Closed the ring with round corner posts and left a deliberate gap on the north side where the stair lands. |
| In the cutaway, the elevator was a flat two-panel screen, not a cage. | Rebuilt it as a complete 4 x 6 ironwork ring (four `19121` panels per level) with a gilded car, tied at every level by a plate course. |
| The oak stair was a row of loose columns with no bonding between risers. | Rebuilt as interlocking plate layers, each running from its riser through to the landing. |
| Street trees were flat stacked plate discs and looked mechanical. | Replaced with three layers of `2417` Plant Leaves 6 x 5, each rotated a quarter turn. |

## Round 3 — exposed elevations

| Observed | Change |
|---|---|
| The left and rear party walls were blank brick fields for four storeys. | Punched a plainer window rhythm into both, backed by the black inner skin — deliberately without the arches and sills used on the street fronts, so the hierarchy between principal and secondary elevations survives. |
| The top view showed a bare glazing field. | Added a cross-bar grid so the skylight reads as a glazed roof with real glazing bars. |

## Final round — driven by the contact report

The whole-scene contact analysis reported **47 connected groups**. Rather than accept the
warning, each group was traced back to a specific part and a bounded joint test was run.

| Evidence | Diagnosis | Change |
|---|---|---|
| `inspect --contacts all` put the cornice and roof in groups of their own, 8 LDU clear of the arcade. | The modules' first layer was emitted 8 LDU below their own `base` anchor plane, so both floated. | Corrected the layer datums; the roof bed is now one packed course spanning the wall heads **and** the gallery ring, and the cornice attaches to the roof rather than to the arcade. |
| Long plate runs formed many small groups. | Successive plate layers were packed identically, so their seams stacked and nothing bridged. | Added a `reverse` packing mode; paired layers are now packed from opposite corners so each course bridges the seams of the one below. |
| `joint-test2` — six offsets of a `3185` lattice stacked on another. | **Nothing connects on top of a `3185`**; its apparent top studs are internal geometry. | Abandoned the two-panel full-height cage; each lattice panel is now base-seated on its own landing, where its four underside receptacles land exactly on the landing's stud row. |
| `4207a` ladder was the last single floating part. | Its only connectors are underside stud receptacles for **flat** mounting; no vertical placement can clutch without a SNOT sub-structure. | Removed it. The fire escape now reads through posts, two-layer grille landings and latticed outboard guards. |
| `joint-test3` — round plates on studs. | **`6141` 1x1 round plates only clutch to each other**, not to an ordinary stud, in this connector metadata. | Rebuilt the signal head from square `3024` plates, which stack correctly. |

Result: **2,297 placements in one connected group**, 15,260 contacts.

Three appearance problems were fixed in the same round:

| Observed in `review-3` | Change |
|---|---|
| The blade sign was a full-height black pylon with white bands — it read as a barcode and competed with the building. | Inverted it to a **pale sign board with dark bands**, matching the photograph, shortened it by two courses and set it on a lower black post. |
| The traffic signal was taller than the street lamps, so three near-identical poles lined the kerb. | Gave the signal a compact three-lens head (top at 216 LDU) and added a shaft to the lamps (top at 240 LDU), so the corner furniture now reads at distinct heights. |
| A pale grey ground-floor band wrapped the blind party walls, reading as a different building. | Made the party walls plain Reddish Brown brick from pavement to cornice and punched ground-floor openings, so the blank band is gone. |
| Street trees on Broadway hid two shopfronts. | Removed the middle planter; two trees remain, clear of the glazing. |

## Assessment against the brief

The thumbnail silhouette is the corner block the brief asked for: unequal Broadway and 3rd
Street wings, a 45° chamfer, a flat roofline under a heavy cornice. The focal hierarchy
works in the home view — the chamfered corner with its blade sign reads first, then the
top-floor arcade and cornice band, then the shopfronts. The three horizontal events
(sill course, arcade springing, cornice) give the elevations depth, and the two-layer wall
puts every window a genuine stud deep so the openings read dark in every view.

The light court is legible in the cutaway: patterned floor, gilded gallery balustrades,
two open cage elevators and the oak stair. Quiet surfaces survive as intended — the roof
deck, the party walls and most of the pavement.

## Known limitations

- The chamfer is a true 45° cut only because `30505` Brick 3 x 3 without Corner provides one
  on the stud grid; the corner bay is three studs wide, not a continuously angled wall.
- The blade sign is a free-standing kerbside pylon. The real sign is bracketed off the
  chamfered corner; a wall-mounted version would need a SNOT sub-structure in the corner bay.
- The fire escape has no continuous ladder between landings, for the connector reason recorded
  above. It is guarded, not climbable.
- The galleries are plate cantilevers off the wall head, doubled with a staggered second
  layer. That is a display-model simplification, not a structural claim.
- `physical_validity` remains `not_proven`. One connected group is connector evidence, not a
  guarantee of clutch strength or stability, and 3,296 overlap candidates remain unproven
  either way — stud-and-socket envelopes legitimately overlap.
- Colour codes are valid LDraw palette entries; they do not assert that every part was
  manufactured in that colour.
