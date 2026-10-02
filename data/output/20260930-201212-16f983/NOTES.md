# Technic car build — working notes

## Request
"build me an impressive Technic car model!" (open-ended; concept chosen by agent)

## User decisions (confirmed)
- Size: MEDIUM (~900 parts)
- Features: ALL — independent suspension (4 wheels), rack steering + HOG knob + steering wheel,
  rear differential, 2-speed gearbox with shift lever, V8 piston engine driven from rear wheels,
  2 opening doors, rear wing.
- Concept: orange/black mid-engine hypercar (wedge body, low nose, cab-forward; V8 visible through
  slatted engine cover; butterfly doors; raised rear wing). Palette: orange body, black trim/wheels,
  dark bluish grey frame/mechanics.

## Environment / availability
- doctor: OK (library /opt/ldraw/ldraw, leocad, jev-rerank, render-steps present)
- Jev availability check (2026-09-30): PASSED — exit 0, 1 result, stats.api_calls=1, key present (not printed).
  → Use Jev semantic discovery (`discover search ... --engine jev`, `jev-rerank`) for part/submodel roles.

## Guides read
instructions.md, technic.md, vehicles.md, mechanisms.md, snapping.md, tooling.md, build-manuals.md,
complex-models.md, technic-atlas README, mechanism-atlas README, vehicle-atlas README.

## Approved 4-phase plan
Phase 1 survey (corpus → signature parts → census.py → census.md → Jev per thin type → shortlist render) → CHECKPOINT 1
Phase 2 brief + layout.json + modules.json (M1..M12) + rough placement render → CHECKPOINT 2
Phase 3 build modules M1→M2→M3→M4→M5→M6→M7→M12→M9/M10→M8→M11
Phase 4 integrate, align_check.py, clash fixes, stance script, visual review, final checks, publish.

Rules: large outputs to files, print summaries only; ≤5 results per search.

## Known source defects (from study reports)
- springMesh raw geometry in shock sections → replace with library shock part
- flex axles / rib hoses (ldcFlex*, technicRibHose*) → rigid replacements
- assembly.nonrigid rounded rotations → --normalize-rotations or redesign
- bfc.invertnext in embedded DATs → --repair-bfc-comments or official part
- part.alias_or_internal → current part

## Progress log
- [x] Phase 0: guides, Jev check, initial model search (output/discovery/)
- [x] Phase 1 survey  (output/prospect/): corpus.json, census.py (read-only), census.json, summarize.py, census.md,
      jev-{gearbox,rearaxle,doors,wing,hog}.json (Jev semantic, 5 each), candidates.json,
      shortlist/ (15 namespaced extractions + manifests, shortlist-board.mpd, board-render/top.png+home.png OPENED)
      Key finding: 42039 (mid-engine 24h race car) is primary donor for M2/M4/M5/M6/M7/M8; 42112 gearshift for M3;
      42093 spoiler for M11; frame/body redesigned. -> WAITING AT CHECKPOINT 1 for user
- [x] Phase 2 plan: design-brief.md (Fiamma V8), layout.json (measured), modules.json (M1-M12 contracts, budget ~911),
      rough placement prospect/rough/rough-layout.mpd -> render right/top/home OPENED (front/back rendered, not opened).
      Key measurements: tyre R=86.118 (installed geometry), donor->car translate (0,20,60), wheelbase 740, track 459,
      engine raised 40 + forward 20 (crank y=-100), gearbox in-line z 570-710 (ring shaft y=-60 = diff pinion, lay y=-100 = crank),
      42112 ratios 16:16 and 20:12. OPEN: front tyres float 8 LDU (fix in M5 or 0.62 deg rake).
      -> WAITING AT CHECKPOINT 2 for user
- [ ] Phase 3 modules
- [ ] Phase 4 integration / review / delivery
