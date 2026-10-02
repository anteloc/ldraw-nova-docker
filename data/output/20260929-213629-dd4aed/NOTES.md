# Bradbury Building — working notes

## STATUS: COMPLETE (2026-09-30)
Final revision built, fully checked, visually reviewed and published.
`output/bradbury.mpd` — 2,297 placements, 15 FILE blocks, ONE connected group.

## Status log
- 2026-09-29: doctor OK (library /opt/ldraw/ldraw, leocad present, shadows loaded).
- 2026-09-29: **Jev availability check PASSED** — `jev-rerank` on PATH, `TYPESAFE_API_KEY` present,
  bounded query `brick` returned 1 result with `stats.api_calls = 1`, exit 0.
  → Semantic discovery via `discover search` / `jev-rerank` was authorized and used for this task.
  No fallback to `--engine fts` was needed; no Jev call failed.
- User scope confirmation: **include the light-court interior** and **include sidewalk street furniture**.
- 2026-09-30: final revision round; contact-driven repairs took the model from 47 connected
  groups to 1. Visual review recorded in `visual-review.md`. Model published.

## Subject
Bradbury Building, 304 S. Broadway at W 3rd St, Los Angeles (George Wyman, 1893).
Exterior corner block + interior light court (atrium) + street furniture.

## Semantic discovery record (Jev, model jev-1.13.0)
| Role queried | Chosen | Score/rank | Decision |
|---|---|---|---|
| "a brick with a cut away diagonal corner for an angled building wall" | `30505` Brick 3x3 without Corner | found via family search after rank-1 `43708` rejected | **ADOPTED** — true 45° cut, grid-legal |
| "a round arch piece spanning a narrow window head in a stone wall" | `3659` Arch 1x4 (80x24) | family expanded from rank-1 `5843` | **ADOPTED** — spans exactly one 80 LDU bay |
| same role, arcade floor | `6182` Arch 1x4x2 (80x48) | — | **ADOPTED** — body 48 = exactly 2 brick courses |
| grand entrance arch | `30613` Arch 3x6x5 Ornamented (120x120x60) | surfaced as `s/30613s01` rank 5 | **ADOPTED** — 120 tall = exactly the ground storey |
| "an ornamental iron railing for a Victorian interior balcony" | `19121` Fence Ornamented 1x4x2 | 0.44 rank-1 was `41823` (quarter round, rejected) | **ADOPTED** (gallery balustrades + elevator cages) |
| elevator cage lattice | `3185` Fence Lattice 1x4x2 | — | **ADOPTED** for the fire-escape guards (see joint test) |
| "a black metal fire escape platform ladder..." | `4207a` Ladder 2.6x14 with Stops | 0.76 rank 1 | **REJECTED after inspection** — connectors are underside stud receptacles for flat mounting only |
| fire escape decking | `2412b` Tile 1x2 Grille with Groove | — | **ADOPTED** |
| "a decorative moulded profile brick for a classical cornice" | all results were **Modulex** (wrong system) | 0.85 | **REJECTED ALL** — used `2877` Brick 1x2 with Grille as the frieze |
| "a fire hydrant for a city street sidewalk" | only Duplo patterns | 0.70 | **REJECTED** — built from round bricks + round tile |
| "a large flat transparent panel for a glass skylight roof" | `6156`, `295`/`4448` glass | 0.80 | **REJECTED** — wrong scale; used Trans-Clear plates on a black kerb and beams |
| "a leafy tree foliage piece for a city street tree" | `2417` Plant Leaves 6x5 | — | **ADOPTED** — three layers, each rotated a quarter turn |
| street lamp | `2039` Support 2x2x7 Lamppost with 6 Base Flutes | — | **ADOPTED** (lamps, signal, sign post) |

Reference-level (submodels) search "a repeating brick facade wall panel with window openings":
top hits are all **Architecture-line microscale** panels (21023 Flatiron, 21043, 21046, 21017 Imperial
Hotel). Scale is wrong for a brick-built wall. Decision: **technique only** — noted the headlight-brick +
centre-stud-plate window trick (21017) and grooved-tile window bands (21023); **nothing copied**.
All façade construction here is original.

## Fixed geometry (LDU; negative Y up; sidewalk top = Y -8)
| Item | Value |
|---|---|
| Bay pitch | 80 (2-stud pier + 2-stud window; 3-stud openings at ground) |
| Course | 24; plate 8 |
| Base plates | 9 x `91405` 16x16 at y 0; X,Z in [-480,480] |
| Building footprint | X [-480, 200], Z [-120, 480] = 34 x 30 studs |
| Street elevations | Broadway faces -Z; 3rd Street faces +X |
| Chamfered corner | `30505` at (170, y, -90), yaw 0 (native cut is +X/-Z) |
| Front bays | 7 · Right bays | 6 |
| Wall layers | outer 1 stud (visible, open at windows), inner 1 stud (Black backing) |
| Light court | cells x 5..28, z 5..24 = 24 x 20 studs |
| Storey pitches | ground 136 (5 courses), typical/arcade 112 (4) |
| Storey origins (scene y) | ground -8, s1 -144, s2 -256, s3 -368, arcade -480, roof -592 |
| Overall model bounds | 980 x 692 x 960 LDU |
| Anchors | every module: `base` [0,8,0]; `next` at its own top plane |

## Connector evidence established by joint tests (reusable facts)
Recorded from `output/joint-test*.plan.json` + `inspect --contacts all`:
- `2039` Support 2x2x7: four **receptacles at its base** (accepts a 2x2 plate's studs) and a
  **single centred male stud on top** → a 1x1 plate/brick centred on top connects.
- A 1x1 part centred on a **2x2 plate** does NOT connect (half-stud parity) — use the 2x2's studs.
- **Nothing connects on top of `3185`** Fence Lattice; its listed top studs are internal.
- **`6141` 1x1 round plate only clutches to another `6141`**, not to an ordinary stud.
- `3024`→`3024`, `3024`→`3062b`, `3062b`→`98138` all connect normally.

## Resolved design problems
- **45° chamfer**: solved with `30505` (grid-legal). Hinge-panel option rejected: exact 45° closure is
  irrational, so it would leave an unsupported flap. Stagger option rejected as crude.
- **Recessed windows**: outer layer open at window cells, inner layer solid Black → real 20 LDU reveal.
- **Plate seams**: added a `reverse` packing mode so paired plate layers are packed from opposite
  corners and each course bridges the seams of the one below. This is what closed most of the
  47 connected groups.
- **Module datums**: cornice and roof first layers were 8 LDU below their own `base` anchor and
  floated; corrected, and the cornice now attaches to the roof bed rather than the arcade.
- **Gallery cantilever**: 4-stud plate cantilever off the wall top, doubled with a second staggered
  plate layer for bonding. Recorded as a display-model simplification.

## Final verification
| Check | Result |
|---|---|
| `build` (assembly + geometry) | passed, no errors |
| `validate --geometry` | `checks_passed: true`; 2 warnings (auto-mode contacts skipped; collision review) |
| `inspect --contacts all` (whole scene) | 2,297 placements, 15,260 contacts, **1 connected group**, 1,221 confirmed groups |
| `bom` | 2,297 placements, 46 distinct part refs, 157 part/colour lines |
| `compare-bom` vs LeoCAD CSV | **exact match**, 0 differences |
| `check-model.sh` | passed, LeoCAD import/snapshot/BOM OK |
| Visual review | 6 whole-model views + 2 cutaway views opened; see `visual-review.md` |

## Files
- `bradbury.mpd` — final model · `bradbury-cutaway.mpd` — interior review variant
- `generate_bradbury.py` — generator (regenerates all three plans)
- `plans/details.plan.json`, `plans/building.plan.json`, `plans/scene.plan.json`, `plans/cutaway.plan.json`
- `design-brief.md`, `visual-review.md`, `NOTES.md`
- `bradbury.validation.json`, `bradbury.bom.json`, `bradbury.bom-comparison.json`,
  `bradbury.inspection.json`, `bradbury-full.json`, `bradbury.build.json`
- `review-final/` (6 views + LeoCAD BOM), `review-court/` (cutaway), `review-1/`..`review-3/` (history)
- `joint-test*.plan.json` / `.mpd` / `.json` — connector evidence tests

## If resuming
Rebuild with:
```sh
.venv/bin/python output/generate_bradbury.py --outdir output/plans
./ldraw-agent build output/plans/scene.plan.json --output output/bradbury.mpd --detail summary --force
```
Keep all geometry fixes in `generate_bradbury.py`; the JSON plans are regenerated and any
direct edit to them is overwritten.
