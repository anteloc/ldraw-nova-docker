
import pathlib
p = pathlib.Path("output/NOTES.md")
s = p.read_text()
s = s.replace("""## Status log
- [x] Plan approved by user.
- [x] doctor, Jev availability.
- [ ] View reference renders (cottage, farmstead).
- [ ] Jev role queries.
- [ ] Verify 48x48 baseplate + crop part geometries.
- [ ] design-brief.json.
- [ ] generator + plans, build, checks, renders, visual review, publish.""",
"""## Status log
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
- [ ] publish_model final revision.""")
p.write_text(s)
print("notes updated")
