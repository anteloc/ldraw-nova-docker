# Tidewater Cabin: working notes

## Files
- Brief: `output/seaside-cabin/brief.md`
- Source generator (the editable source): `output/seaside-cabin/generate.py`
- Generated plan: `output/seaside-cabin/cabin.plan.json`
- Built MPD (reviewed copy): `output/seaside-cabin/review/model.mpd`
- Review folder: `output/seaside-cabin/review/` (review.json, validation.json, bom.json, bom-comparison.json, previews/)
- Earlier no-render check: `output/seaside-cabin/checks/`

## Checks
- `doctor`: passed (python, pyldraw3, library, LeoCAD all present).
- Build: passed (173 physical placements).
- Review: `checks_passed: true`, validation, BOM, render and BOM comparison all passed. `physical_validity: not_proven`.
- Warnings left: `assembly.disconnected_evidence` (33-34 separate groups: the garden items, the porch, and the roof stacked on bricks, not connected by studs) and `coverage.collision_review` (some parts lack rectangular body checks).

## Issues found and fixed during the build
1. Colour 221 is not a valid palette code. Dark Pink is code 5 (catalog lookup).
2. Garden path tiles overlapped at 20 LDU spacing. Spacing is now 40 LDU.
3. Planters and plants overlapped the deck. Moved to z=170.
4. Part 3023 is marked "~Moved to 3023b". The glazing and the door use 3023b.
5. Roof rows floated over the interior. Added an attic ceiling (three 2x4 bricks) so the upper roof rows sit on bricks.
6. First render: brown box, no door, no contrast. Upper storey, gable and ceiling are now white; the door is a red 1x2 plate stack.

## Visual review (images opened)
- `previews/home.png`: reads as a two-storey cabin: brown plinth and ground floor, white upper storey, dark slate roof. Windows are recessed glass.
- `previews/front.png`: door and windows visible; the gable is a flat triangle of white.
- `previews/top.png`: garden path and planters visible at the sea side.

## Deviations from the brief
- Upper storey is NOT set back one stud; it is the same footprint, to keep the bricks interlocking.
- No chimney, cupola, porch roof, deck rails, fence, bench or buoy. These were in the brief and are not built yet.
- Trim: the brief's off-white trim is only used for the upper storey, not as window frames.
- Interior floors and furniture are not modelled.

## Next actions if continuing
- Add a chimney on a clear roof bay, a porch roof, and a low picket fence along the path.
- Add a cupola on the ridge with a porthole.
- Consider white window sills, supported on the course below.
