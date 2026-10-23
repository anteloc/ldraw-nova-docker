# Notes: sideways-stud lighthouse

## Brief
- output/lighthouse/brief.md (written before the plan)

## Jev availability
- Prerequisites present: jev-rerank on PATH, data/ldraw-info.db present, TYPESAFE_API_KEY set (value not printed).
- Live query `jev-rerank ... --query 'brick' --top 1 --candidates 1 --model jev-1.13.0 --no-score-cache --timeout 10 --retries 0 --json` returned one ranked result with exit 0.
- Jev was not needed further: parts were chosen from the SNOT guide, the parrot connector data and direct `part` inspection.

## Sources and generator
- Generator: output/lighthouse/generate.py -> output/lighthouse/lighthouse.plan.json
- Build/review: `./ldraw-agent review output/lighthouse/lighthouse.plan.json --outdir output/lighthouse/review --force`
- Reused connection knowledge: 67329 studs-on-3-sides wall, from examples/snot/parrot (inspected connectors; not copied geometry). No example plan was copied.

## Geometry verified
- Bricks use top face as origin, body extends +Y (confirmed by `part` bounds: 3003 y 0..24, 3022 y 0..8).
- 67329: body x ±20, z ±10, y 0..40; studs on the -Z face point outward after yaw 0/90/180/270.
- Yaw convention: yaw 0 maps local -Z to -Z; 90 maps to -X; 180 to +Z; 270 to +X.
- Plinth top at Y=-48; tower storeys at top Y = -88 - 40n; 4 storeys; ytop = -208.

## Review 1 (before fix)
- checks_passed true; validation/bom/render/bom_comparison passed; 88 placements.
- Warning: 2 optimistic groups. Cause: 1x1 yellow beacon (3024) at the centre of a 2x2 roof cap, not on any stud.
- Fix: beacon changed to 3022 2x2 yellow plate on the cap studs.

## Review 2 (final candidate)
- checks_passed true; all four stages passed; 88 physical placements.
- Remaining warning: coverage.collision_review (some parts lack rectangular body checks).
- Previews opened: front.png, home.png, top.png (review 2).

## Visual findings
- Good: outward SNOT studs read clearly on four faces; red band; dark door at the base; glazed lantern; gallery ring; top view shows 4x4 deck around the 2x2 lantern.
- Weak: the tower is a straight square box, not the octagonal taper promised in the brief. The 2x2 core and 67329 wall depth fix the section at 80 LDU.
- Weak: roof is a flat 2x2 plate, not a dome or cone, so the silhouette is less lighthouse-like.
- Weak: no gallery railing; the window is only one clear wall brick in storey 3.

## Deviations from the proposal
- Square section, not octagonal; no taper.
- Flat roof cap, not dome.

## Next actions (if continuing)
- Add a taper by reducing the upper-storey section (new wall positions and core removal).
- Add a dome roof using slope bricks, and a railing on the gallery.
- Re-run review and inspect home/front/top after any change.
