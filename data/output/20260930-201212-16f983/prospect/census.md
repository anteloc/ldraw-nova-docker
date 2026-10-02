# Technic car subassembly census

Corpus: 9 cars (42039, 42096, 8880, 8865, 42093, 42111, 8448, 42056, 42083); 15042 physical placements. Source: `census.py` (read-only, pyldraw3 parse). Units = named sections, or instruction-step runs of flat sections with >100 direct placements, merged by identifying-part tag. Position is the unit centroid along the car length (0 = front, set by steering parts). Neighbours = other units whose part origins are within 25 LDU; axle crossings = other units whose part origins lie on this unit's axle segments (≤12 LDU off axis). All are approximations from origins, not solid geometry.

## Frequency by family

| Family | Cars (of 9) | Units | Median parts/unit | Typical position | Common identifying parts | Usual neighbours / axle crossings |
|---|---:|---:|---:|---|---|---|
| frame / chassis | 9 | 112 | 17 | middle 45, rear 34 | 42093 - 35185.dat | nb: body panels, steering (rack/column/input), axle suspension / knuckles; ax: body panels, gearbox, axle suspension / knuckles |
| piston engine | 9 | 43 | 22 | rear 24, front 19 | 2851.dat, 2850b.dat, 2854.dat, 2850a.dat, 3652.dat | nb: unclassified, frame / chassis, body panels; ax: gearbox, unclassified, axle suspension / knuckles |
| rear axle + differential | 9 | 18 | 16 | rear 14, front 2 | 3712c01.dat, 62821.dat, 92906.dat, 6573.dat, 73071.dat | nb: axle suspension / knuckles, frame / chassis, unclassified; ax: unclassified, axle suspension / knuckles, frame / chassis |
| steering (rack/column/input) | 9 | 31 | 18 | front 13, middle 12 | 3743.dat, 2741.dat, 2739a.dat, 3712.dat, 2819.dat | nb: frame / chassis, axle suspension / knuckles, driveline (UJ/CV shafts); ax: axle suspension / knuckles, wheels, doors |
| axle suspension / knuckles | 8 | 50 | 21 | front 22, rear 15 | 4255.dat, 4254.dat, 11950.dat, 57515.dat, 2738.dat | nb: frame / chassis, steering (rack/column/input), rear axle + differential; ax: unclassified, driveline (UJ/CV shafts), rear axle + differential |
| body panels | 8 | 113 | 14 | front 42, rear 40 | — | nb: frame / chassis, unclassified, axle suspension / knuckles; ax: frame / chassis, lights, axle suspension / knuckles |
| driveline (UJ/CV shafts) | 8 | 13 | 12 | front 6, middle 4 | 3712.dat, 62520.dat, 3326b.dat, 62519.dat, 92906.dat | nb: axle suspension / knuckles, steering (rack/column/input), frame / chassis; ax: steering (rack/column/input), axle suspension / knuckles, wheels |
| wheels | 8 | 17 | 16 | middle 9, rear 5 | 32494.dat, 15038.dat, 44771.dat, 23799.dat, 42610.dat | nb: axle suspension / knuckles, frame / chassis, steering (rack/column/input); ax: gearbox, body panels, piston engine |
| doors | 7 | 18 | 17 | middle 14, rear 3 | 32028.dat | nb: frame / chassis, body panels, steering (rack/column/input); ax: gearbox |
| gearbox | 7 | 46 | 13 | middle 27, rear 13 | 18946.dat, 18948.dat, 6542a.dat, 18947.dat, 6641.dat | nb: frame / chassis, body panels, axle suspension / knuckles; ax: frame / chassis, axle suspension / knuckles, body panels |
| lights | 7 | 21 | 13 | front 12, rear 9 | — | nb: body panels, frame / chassis, rear wing / spoiler; ax: frame / chassis |
| unclassified | 7 | 69 | 8 | rear 36, middle 23 | 32494.dat | nb: frame / chassis, axle suspension / knuckles, body panels; ax: axle suspension / knuckles, lights, wheels |
| cockpit / seats | 6 | 19 | 24 | middle 12, front 7 | 87752.dat | nb: frame / chassis, body panels, gearbox; ax: — |
| rear wing / spoiler | 5 | 17 | 26 | rear 13, front 4 | — | nb: body panels, unclassified, lights; ax: gearbox, frame / chassis |
| exhaust | 3 | 5 | 14 | rear 5 | — | nb: piston engine, frame / chassis, rear wing / spoiler; ax: — |

## Candidate units in medium source cars (role=source)

### rear axle + differential

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 8865 `8865 - Vehicle.ldr` | 21 | [6, 6] | middle 0.61 | 100 | 73071.dat×1 | driveline (UJ/CV shafts) |
| 8880 `8880 - main.ldr` | 19 | [3, 6] | middle 0.51 | 74 | 6573.dat×1 | frame / chassis, unclassified |
| 8880 `8880 - step15.ldr` | 18 | all | front 0.23 | 100 | 6573.dat×1; 3712c01.dat×2 | unclassified, axle suspension / knuckles |
| 8880 `8880 - step15.ldr` | 18 | all | rear 0.81 | 100 | 6573.dat×1; 3712c01.dat×2 | unclassified, axle suspension / knuckles |
| 8865 `8865 - Rear Axis Mounting.ldr` | 16 | all | rear 0.81 | 75 | — | — |
| 8865 `8865 - Rear Axis Mounting.ldr` | 16 | all | rear 0.81 | 75 | — | — |
| 42039 `42039 - 24 Hours Race Car.ldr` | 14 | [2, 2] | rear 0.85 | 100 | 62821.dat×1; 92906.dat×2 | — |
| 42096 `42096 - porsche.ldr` | 10 | [1, 1] | rear 0.78 | 100 | 92906.dat×2; 62821.dat×1 | steering (rack/column/input) |

### axle suspension / knuckles

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 8865 `8865 - Vehicle.ldr` | 80 | [19, 22] | middle 0.38 | 50 | — | — |
| 42096 `42096 - frontaxle.ldr` | 71 | all | front 0.27 | 89 | 57515.dat×4; 4254.dat×2; 92909.dat×2; 2739a.dat×2 | steering (rack/column/input) |
| 42039 `42039 - frontaxle.ldr` | 62 | all | front 0.24 | 90 | 57515.dat×4; 4255.dat×2; 11949.dat×2; 92909.dat×2; 11949.dat×2 | — |
| 8865 `8865 - Vehicle.ldr` | 43 | [11, 12] | middle 0.57 | 100 | — | axle suspension / knuckles |
| 8880 `8880 - main.ldr` | 40 | [24, 24] | middle 0.42 | 88 | 2909.dat×8; 2910.dat×8 | — |
| 8865 `8865 - Vehicle.ldr` | 37 | [3, 4] | middle 0.49 | 27 | — | — |
| 8865 `8865 - Vehicle.ldr` | 35 | [1, 1] | middle 0.61 | 94 | — | axle suspension / knuckles |
| 8865 `8865 - Vehicle.ldr` | 35 | [9, 9] | middle 0.4 | 54 | 73129.dat×8 | axle suspension / knuckles |

### steering (rack/column/input)

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 42096 `42096 - porsche.ldr` | 385 | [40, 107] | middle 0.46 | 92 | — | doors |
| 42096 `42096 - porsche.ldr` | 155 | [12, 36] | middle 0.54 | 99 | — | steering (rack/column/input) |
| 8880 `8880 - step28.ldr` | 52 | all | middle 0.35 | 27 | 2741.dat×1; 2741.dat×1 | — |
| 8865 `8865 - Vehicle.ldr` | 39 | [8, 8] | middle 0.52 | 41 | 3743.dat×2; 3712.dat×4; 3326b.dat×2 | rear axle + differential, wheels |
| 42096 `42096 - steering.ldr` | 25 | all | front 0.31 | 92 | 87761.dat×1 | axle suspension / knuckles, steering (rack/column/input) |
| 42039 `42039 - steeringrack.ldr` | 22 | all | front 0.27 | 100 | 87761.dat×1; 32005.dat×2 | — |
| 42096 `42096 - porsche.ldr` | 18 | [2, 3] | rear 0.79 | 89 | — | axle suspension / knuckles, wheels, steering (rack/column/input), axle suspension / knuckles |
| 42096 `42096 - porsche.ldr` | 18 | [110, 111] | rear 0.8 | 44 | — | — |

### piston engine

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 42096 `42096 - engine.ldr` | 69 | all | rear 0.68 | 97 | 2850b.dat×6; 2851.dat×6 | — |
| 42039 `42039 - motor.ldr` | 66 | all | rear 0.66 | 77 | 2851.dat×8; 2854.dat×3 | unclassified, axle suspension / knuckles, frame / chassis |
| 8865 `8865 - Motor Block.ldr` | 53 | all | rear 0.78 | 91 | 3652.dat×4 | — |
| 8865 `8865 - Cylinder Block.ldr` | 34 | all | rear 0.79 | 47 | — | — |
| 8865 `8865 - Cylinder Block.ldr` | 34 | all | rear 0.79 | 47 | — | — |
| 8880 `8880 - step27-1-5.ldr` | 25 | all | rear 0.81 | 92 | 2851.dat×8; 2854.dat×3 | piston engine, unclassified |
| 42096 `42096 - roof3.ldr` | 24 | all | rear 0.79 | 100 | — | — |
| 8880 `8880 - step23.ldr` | 22 | all | front 0.03 | 0 | — | — |

### gearbox

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 42096 `42096 - front.ldr` | 39 | all | front 0.05 | 95 | 18948.dat×1 | — |
| 8880 `8880 - step13.ldr` | 26 | all | middle 0.45 | 100 | 6542a.dat×4; 6539.dat×2 | — |
| 8880 `8880 - main.ldr` | 19 | [22, 22] | middle 0.41 | 11 | 6543.dat×1 | — |
| 42039 `42039 - 24 Hours Race Car.ldr` | 17 | [34, 35] | middle 0.51 | 100 | 18946.dat×2; 18948.dat×1 | — |
| 8880 `8880 - main.ldr` | 12 | [36, 36] | middle 0.52 | 0 | 2998.dat×4; 2997.dat×4; 168315c.dat×1; 168315b.dat×1 | — |
| 42039 `42039 - 24 Hours Race Car.ldr` | 8 | [43, 43] | middle 0.47 | 100 | 6542b.dat×1 | — |

### driveline (UJ/CV shafts)

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 8865 `8865 - Vehicle.ldr` | 78 | [16, 18] | front 0.21 | 64 | 3712.dat×4; 3326b.dat×2 | axle suspension / knuckles |
| 8865 `8865 - Vehicle.ldr` | 36 | [7, 7] | rear 0.67 | 81 | 3712.dat×4; 3326b.dat×2 | steering (rack/column/input) |
| 8865 `8865 - Vehicle.ldr` | 32 | [5, 5] | middle 0.36 | 97 | 3712c01.dat×1 | — |
| 8865 `8865 - Vehicle.ldr` | 30 | [14, 14] | middle 0.59 | 87 | 3712c01.dat×1 | driveline (UJ/CV shafts) |
| 42096 `42096 - porsche.ldr` | 10 | [37, 37] | middle 0.4 | 100 | 62520.dat×4; 62519.dat×2 | steering (rack/column/input), steering (rack/column/input) |
| 8880 `8880 - step21sub1.ldr` | 9 | all | front 0.25 | 100 | 3712.dat×2; 3326b.dat×1 | steering (rack/column/input), unclassified |
| 8880 `8880 - step21sub2.ldr` | 9 | all | front 0.29 | 100 | 3712.dat×2; 3326b.dat×1 | — |

### cockpit / seats

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 42096 `42096 - dashboard.ldr` | 43 | all | middle 0.38 | 84 | — | — |
| 42096 `42096 - headlight1.ldr` | 33 | all | front 0.28 | 91 | 87752.dat×1 | — |
| 42096 `42096 - headlight2.ldr` | 33 | all | front 0.28 | 91 | 87752.dat×1 | — |
| 42096 `42096 - seat1.ldr` | 26 | all | middle 0.57 | 100 | — | — |
| 8865 `8865 - Seat.ldr` | 23 | all | middle 0.56 | 0 | — | — |
| 8865 `8865 - Seat.ldr` | 23 | all | middle 0.56 | 0 | — | — |
| 42039 `42039 - seat.ldr` | 12 | all | middle 0.48 | 100 | — | — |

### doors

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 42096 `42096 - door1.ldr` | 32 | all | middle 0.45 | 88 | — | — |
| 42096 `42096 - door2.ldr` | 32 | all | middle 0.45 | 88 | — | — |
| 42039 `42039 - doorlift2.ldr` | 16 | all | rear 0.67 | 94 | — | gearbox |
| 42039 `42039 - doorlift.ldr` | 10 | all | middle 0.57 | 100 | — | — |

### rear wing / spoiler

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 8880 `8880 - step30sub2.ldr` | 29 | all | front 0.26 | 38 | — | — |
| 8880 `8880 - step31sub2.ldr` | 26 | all | rear 0.63 | 38 | — | gearbox |
| 8880 `8880 - step31sub1.ldr` | 26 | all | rear 0.63 | 38 | — | gearbox |
| 8880 `8880 - step10sub2.ldr` | 20 | all | front 0.09 | 25 | — | — |
| 42096 `42096 - rear2.ldr` | 19 | all | rear 0.97 | 89 | — | — |
| 42096 `42096 - rear3.ldr` | 19 | all | rear 0.97 | 89 | — | — |
| 8880 `8880 - step35.ldr` | 17 | all | rear 0.92 | 6 | — | — |
| 42096 `42096 - spoiler.ldr` | 15 | all | rear 0.97 | 100 | — | — |

### frame / chassis

| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |
|---|---:|---|---|---:|---|---|
| 42039 `42039 - 24 Hours Race Car.ldr` | 239 | [8, 33] | middle 0.52 | 98 | — | gearbox, body panels, axle suspension / knuckles |
| 8865 `8865 - Front Frame.ldr` | 63 | all | front 0.31 | 56 | — | — |
| 8880 `8880 - step30sub1.ldr` | 45 | all | middle 0.59 | 51 | — | — |
| 8880 `8880 - main.ldr` | 45 | [20, 21] | middle 0.51 | 71 | — | — |
| 42039 `42039 - hood.ldr` | 43 | all | rear 0.96 | 100 | — | body panels |
| 42039 `42039 - frontfloor.ldr` | 28 | all | front 0.07 | 100 | — | — |
| 8880 `8880 - step33.ldr` | 27 | all | rear 0.81 | 74 | — | — |
| 42039 `42039 - frontchassis.ldr` | 26 | all | middle 0.38 | 100 | — | — |


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
