# Willowbank Cottage — build notes

## Request
"plan first, and then, build me a beautiful cottage, a large one, with a small field at the back, and some growing vegetables" — plan approved 2026-10-03.

## Discovery status
- doctor: OK (pyldraw3 1.7.0, library /opt/ldraw/ldraw, leocad + jev-rerank + mpd2glb.sh + ldraw-render-steps.sh present).
- Jev: AVAILABLE. Probe `brick --top 1 --candidates 1` exit 0, api_calls=1, score 0.48.
- Semantic part-role queries to run: pumpkin, leafy greens, root vegetable, vine/trellis, garden gate, tree/bush.

## Design summary (see design-brief.json)
- 48x48 baseplate (verify 30342; fallback 3811 32x32 with tighter field).
- Hall: 20x14, rows=12 (2 storeys), door X=+4, two window rows. Roof: gable w22 d14 dormer.
- Wing: 10x10 rear-left, rows=6, own gable, back door to field.
- Chimney at ridge; porch w8 + stairs; front path.
- Field ~28x12 behind: 5 soil beds (dark tan tiles), pumpkin/carrot/leafy/flower beds, trellis+vine on rear fence, gate at path.
- Palette: Tan body / White trim / Dark Green roof / Reddish Brown door+fence / Dark Tan stone / Trans Light Blue glass / Green grass.

## Modules (planned sections)
willowbank-scene.ldr (main), hall-shell.ldr, hall-roof.ldr, wing-shell.ldr, wing-roof.ldr,
porch/stairs/chimney (helpers), garden-field.ldr, veg-*-bed.ldr, vine-trellis.ldr.

## Status log
- [x] Plan approved by user.
- [x] doctor, Jev availability.
- [x] View reference renders (cottage, farmstead).
- [x] Jev role queries: pumpkin 51270 (0.83); leafy 6255/7264/2417/2423;
      root veg 37681 (0.54); vine 16981 (0.79); gate 3186/3358 (0.74).
- [x] Baseplate 4186 (48x48, -480..480) verified; all crop/door/slope bounds measured.
- [x] design-brief.json written BEFORE generator.
- [x] generator + scene.plan.json -> willowbank-cottage.mpd:
      1,124 plan placements (1,163 physical incl. roof/fence sub-parts).
- [x] Collisions fixed: soil tiles 3034->3068b slabs (h=8), tilled tiles h=16,
      paths cleared of steps/beds, fence corners inset (fence-9 sides),
      removed colliding planter, vine moved to z=19.
- [x] Chimney sign bug fixed (h=472 -> base at ridge tile top y=-472).
- [x] Stray shutter blades (3856 at x=+/-21 studs) removed; plain windows only.
- [x] build --force: checks_passed, 0 errors; warnings: collision_review
      (non-rectangular crops), contacts auto-skip on full scene.
- [x] validate --geometry --contacts all: passed; 205 optimistic components
      (crop/flower/fence leaves without connector metadata; all crops measured
      to seat exactly on soil y=-16).
- [x] garden-field.ldr section inspect --contacts all: 0 errors.
- [x] BOM compare vs LeoCAD: matches True, 1163 = 1163, no differences.
- [x] Renders home/front/back/right/top + field detail; visual review done,
      shutter-ladder + bench fixes verified in re-render (visual-review.md).
- [ ] publish_model final revision.
