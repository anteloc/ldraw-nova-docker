# Willowbank Cottage — visual review

## Views opened
- `review/home.png` (3/4 front), `review/front.png`, `review/back.png`,
  `review/right.png`, `review/top.png` — whole model
- `detail/home.png` — isolated `garden-field.ldr` (vegetable beds)
- `detail/home.png` (earlier) — isolated `leaf-tree-288-5.ldr`, to trace a stray artifact

## What reads well at thumbnail
- The tall two-storey hall with its dark-green gable, chimney and dormer is the
  clear vertical mass; the low kitchen wing gives the "cottage" two-volume
  asymmetry. Recognizable as a house-with-garden at a glance.
- The fenced vegetable field sits cleanly behind the house with visible crop
  colour (orange, pink, greens) and a tan path leading to the gate.
- Palette is controlled: tan walls, white trim, dark-green roof, reddish-brown
  wood/deck, green grass. No scattered accent colours.

## Problems found and fixed
1. **Stray white vertical "ladder" lines** flanking the front facade.
   Isolated the tree module (clean), then dumped all white placements and found
   the cause: the two `3856` (Window 1x2x3 Shutter) blades of the shuttered
   window were placed at local `x=±21`, i.e. ~210 LDU out to each side, floating
   as thin white columns. Fix: removed the `window4_shuttered` variant; all
   bays use the plain `3853/60608` window. Verified the lines are gone in the
   re-render.
2. **Bench crowding the porch** in the front 3/4 view — the earlier extra planter
   was removed (kept the left one), and the bench reads fine beside the path.

## Remaining, lower priority (noted, acceptable)
- The right-front bench is close to the porch steps but does not block the
  four-stud entry; kept as a small seating accent.
- `assembly.disconnected_evidence` (205 groups) and `coverage.collision_review`
  are expected: individual crop plants, flowers, fence rails and the two trees
   rest on soil tiles / baseplate where the connector shadow has no metadata.
  Each crop part's local bounds were measured so its world base sits exactly on
  the soil surface (y=−16 for the raised beds); they are supported, just not
  metadata-connected. The building itself is a single connected shell+roof.

## Scope
Exterior composition and field review from the five whole-model views plus two
isolated module renders. Hidden interior interfaces, real-world clutch strength
and physical buildability are not certified by this review.
