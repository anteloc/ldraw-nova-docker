findings = r'''
## Findings (Phase 1)

**Frequency (9 cars):** frame, piston engine, rear axle + differential and steering occur in 9/9; axle suspension/knuckles,
UJ/CV driveline, body panels and wheels in 8/9; doors, gearbox and lights in 7/9; cockpit/seats 6/9; rear wing 5/9; exhaust 3/9.

**Placement pattern:** differentials sit at the rear in 14 of 18 units (front ones = AWD: 8880, 42083). Engines are rear/mid in
5 cars (42039, 42096, 8880, 8865, 42056 + mid W16 42083) and front in 3 (42093, 42111, 8448). Gearbox units cluster mid-car
(27 of 46), between cockpit and engine. Approximate axle crossings: steering → knuckles/wheels; engine → gearbox/suspension
(engines are driven from the wheels); gearbox → frame/suspension.

**Typical complete-unit sizes (medium cars):** front axle 62–71 parts; V8/flat-6 engine 53–69; steering rack 22–25;
differential stage 14–18; gearbox 17–26; seat 12–26; door 14–32; spoiler 11–19.

**Source defects that affect reuse:** shock sections embed a raw-geometry spring (`*_springMesh.ldr`) -> replace with a library
shock; flex axles/rib hoses are pseudo-parts; rounded rotations normalized on extraction. 42039 `frontaxle` extraction exits 1
because of the spring meshes (other 14 shortlisted extractions exit 0).

## Shortlist board (rendered and inspected)

`shortlist/shortlist-board.mpd` -> `shortlist/board-render/top.png`, `home.png` (both opened). Grid rows: M2-M4 / M5-M6 / M7-M11.

| Module | Primary candidate | Alternative | Notes from images + census |
|---|---|---|---|
| M2 rear axle + diff | 42039 main step 2 (62821 diff + 92906 CV joints, 14 parts) | 8880 `step15` (6573 diff + UJ half-shafts, 18) | both suit independent suspension; 42039 is modern & compact |
| M3 gearbox | 42112 `gearshift` (driving ring + clutch gears, 17) | 42039 main steps 34-35 (18946x2 + 18948, 17); 8880 `step13` 4-speed (460 LDU long) | 2-speed target -> compact driving-ring unit |
| M4 V8 | 42039 `motor` (8 pistons, 66) | 8880 `step27-1-5` + heads | 42039 block is complete and readable; mid-engine donor |
| M5 front axle | 42039 `frontaxle` (62/84, ~21 st wide by origins) | 42096 `frontaxle` (71/96, ~19 st) | both need spring-mesh shock fix; 42039 matches its own rack |
| M6 steering | 42039 `steeringrack` (87761 rack, 22) + vertical input shaft seen in frontaxle | 42096 `steering` (25); 5767 column (8) | HOG + wheel to be added |
| M7 seats | 42039 `seat` x2 (12) | 42096 `seat1` (26) | recolour to black |
| M8 doors | 42039 `doorlift`/`doorlift2` hinge concept + orange panel skin like 42099 `door1` (14) | 42096 `door1` (32) | butterfly doors |
| M11 wing | 42093 `spoiler` (11) on new raised supports | 42096 `spoiler` (15, ~23 st wide - too wide) | |
| M1 frame, M9/M10 body | redesign (pattern: 42039 main steps 8-33, 239 parts, 98% Technic) | - | own silhouette/body = originality |
'''
open('output/prospect/census.md','a').write(findings)
n=open('output/NOTES.md').read()
n=n.replace("- [ ] Phase 1 survey  (output/prospect/)","""- [x] Phase 1 survey  (output/prospect/): corpus.json, census.py (read-only), census.json, summarize.py, census.md,
      jev-{gearbox,rearaxle,doors,wing,hog}.json (Jev semantic, 5 each), candidates.json,
      shortlist/ (15 namespaced extractions + manifests, shortlist-board.mpd, board-render/top.png+home.png OPENED)
      Key finding: 42039 (mid-engine 24h race car) is primary donor for M2/M4/M5/M6/M7/M8; 42112 gearshift for M3;
      42093 spoiler for M11; frame/body redesigned. -> WAITING AT CHECKPOINT 1 for user""")
open('output/NOTES.md','w').write(n)
print('ok')