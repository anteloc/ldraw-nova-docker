import json
layout = {
 "frame": "Car frame: X across (+X = driver/left side), -Z forward, Y=0 road, negative Y up, Z=0 front-axle centreline; units LDU",
 "donor_transform": {"42039_world_to_car": {"translate": [0, 20, 60]},
    "derivation": "42039 rear tyre centre Y=-106.118 + tyre radius 86.118 -> road at donor Y=-20; donor front axle Z=-60 -> 0",
    "note": "all 42039-derived modules keep their donor relative transforms; add this translation (plus listed per-module offsets)"},
 "wheels": {"rim": "15038.dat (Wheel Rim 34 x 56, 6 spokes, 6 pegholes)", "tyre": "44771.dat (Tyre 35/46 x 56 ZR)",
    "tyre_radius_measured": 86.118, "tyre_width": 88, "rim_radius": 70, "source": "ldraw-agent part 44771/15038 (installed geometry; DB cache radius 96 was wrong)",
    "colours": {"tyre": 0, "rim": 179}},
 "axles": {
    "front": {"z": 0, "tyre_centre_x": [-229.6, 229.6], "wheel_centre_y_donor_pose": -94.1,
              "wheel_centre_y_target": -86.1, "open_issue": "front tyres 8 LDU above road in donor pose; resolve in M5 by re-posing arms, else whole-car rake 0.62 deg"},
    "rear": {"z": 740, "tyre_centre_x": [-229.2, 229.2], "wheel_centre_y": -86.1}},
 "wheelbase": 740, "track_tyre_centres": 459, "tyre_outer_x": 273.6,
 "body_planned": {"nose_tip": {"z": -250, "y": -110}, "tail": {"z": 970, "y": -190}, "length": 1220,
    "half_width": 290, "roof": {"y": -270, "z": [200, 330]}, "windscreen_base": {"z": 60, "y": -170},
    "beltline_y": -180, "sill_y": [-40, -100], "front_overhang": 250, "rear_overhang": 230,
    "arches": {"front_cut_y": -190, "rear_cut_y": -200, "clearance_to_tyre_min": 10}},
 "ground_clearance": {"frontaxle_bottom_y": -43, "donor_engine_bottom_y": -35, "engine_bottom_after_raise_y": -75, "target_min": 35},
 "powertrain": {
    "engine": {"type": "longitudinal V8 (42039 motor)", "crank_axis": {"x": 0, "y": -100}, "block_z": [410, 570],
               "placement_offset_from_donor": [0, -40, -20], "top_y": -166},
    "gearbox": {"type": "2-speed driving ring (42112 pattern)", "ring_shaft": {"x": 0, "y": -60, "role": "input from diff pinion"},
                "lay_shaft": {"x": 0, "y": -100, "role": "output to crank"}, "shaft_spacing": 40, "z_window": [570, 710],
                "ratios": ["16T clutch : 16T (1:1)", "20T dbl-bevel clutch 35185 : 12T 6589/32270 (5:3)"]},
    "differential": {"part": "62821.dat", "axle_z": 740, "pinion_shaft": {"x": 0, "y": -60}}},
 "steering": {"rack": {"part": "87761.dat", "z": 60, "y": -80}, "pinion": {"part": "32270.dat", "z": 60, "y": -100, "axis": "Z"},
    "hog": {"vertical_shaft": {"x": 0, "z": -60}, "knob_y": -175, "note": "pinion axle extended forward; 12T bevel pair to vertical shaft"},
    "wheel": {"centre": [80, -190, 170], "transfer": "gear train x 0->80 at z~150, y=-100, then UJ column"}},
 "cockpit": {"seat_centres_x": [-80, 80], "seat_z": [195, 355], "driver_x": 80, "console": {"x": [-30, 30], "shift_lever_z": 300},
    "firewall_z": 380},
 "doors": {"style": "butterfly", "hinge_zone": {"z": 90, "y": -210}, "opening": {"z": [110, 400], "y": [-60, -250]}},
 "wing": {"z": [900, 960], "y": -300, "half_span": 230, "supports_x": [-60, 60]},
 "rough_placement": {"mpd": "prospect/rough/rough-layout.mpd", "renders_opened": ["right.png", "top.png", "home.png"],
    "findings": ["no gross clash between donor units at planned transforms",
                 "engine block (raised 40, forward 20) ends ~40-45 LDU behind seat backs -> firewall 1 beam thick",
                 "gearbox fits Z 570-710 under engine rear shaft",
                 "front tyres float ~8 LDU (confirmed visually)",
                 "42093 spoiler placeholder is only ~11 studs wide -> M11 must widen blade"]}}
json.dump(layout, open('output/layout.json','w'), indent=1)

def mod(id,name,route,source,features,budget,origin,envelope,interfaces,deps,checks,notes=""):
    return dict(id=id,name=name,route=route,source=source,features=features,parts_budget=budget,local_origin=origin,
                envelope_car_frame=envelope,interfaces=interfaces,depends_on=deps,checks=checks,notes=notes,status="planned")
TECH=["build --detail summary","validate --geometry --contacts all","technic check --contract (fixed members)","render home top front bottom","compare-bom"]
MECH=["build --contacts none","validate --geometry --contacts none","render home top front bottom","compare-bom","align_check.py shafts"]
modules=[
 mod("M1","Frame / tub","redesign (pattern: 42039 main steps 8-33)","42039-1.mpd main steps 8-33 (study only)",[],120,
     "car frame (placed at identity)",{"x":[-200,200],"y":[-200,-40],"z":[-240,900]},
     {"provides":["front-axle mount holes (from donor frontaxle study)","rear-axle mount holes (donor steps 1-7)","raised engine cradle (crank y=-100)",
                  "gearbox bearing beams (shafts y=-60/-100, z 570-710)","seat mounts x=+-80","console / shift pivot","door hinge hoop z~90","firewall hoop z~380",
                  "sill body rails y~-60..-100 x~+-200","rear subframe z 800-900 for wing supports and diffuser"]},
     [],TECH,"Mount-hole list is filled from the donor-unit interfaces during Phase 3 study before M1 is generated."),
 mod("M2","Rear axle + differential + independent suspension","adapt","42039-1.mpd main steps 1-7 (81 lines incl. 2 shock submodels)",
     ["differential","independent suspension"],85,"donor 42039 world + layout.donor_transform",{"x":[-274,274],"y":[-212,-20],"z":[630,850]},
     {"shafts":[{"id":"S1","axis":"Z","x":0,"y":-60,"to":"M3 ring shaft","note":"diff pinion shaft"}],
      "mounts":"pins into M1 rear subframe (list from study)"},["M1"],MECH,
     "Replace shock-06_5L-hard-1 spring mesh with library shock 73129 (6.5L complete); remove donor crank direct-drive link."),
 mod("M3","2-speed gearbox + shift linkage","adapt","42112-1.mpd '42112 - gearshift.ldr' (17 parts) + new linkage",["gearbox + shift lever"],35,
     "gearshift local frame rolled 90 deg about Z (local X -> car +Y), origin at (0,-80,700)",{"x":[-40,120],"y":[-130,-30],"z":[560,720]},
     {"shafts":[{"id":"S1","from":"M2"},{"id":"S2","axis":"Z","x":0,"y":-100,"to":"M4 crank"},
                {"id":"S3","kind":"shift rod","path":"console lever (z~300) -> along x~+100 beside engine -> fork at z~640"}]},["M1","M2"],MECH),
 mod("M4","V8 engine","reuse (shortened rear shaft)","42039-1.mpd '42039 - motor.ldr' (66 parts)",["V8 piston engine"],66,
     "donor transform + offset (0,-40,-20)",{"x":[-74,74],"y":[-166,-75],"z":[410,590]},
     {"shafts":[{"id":"S2","from":"M3"}],"mounts":"engine cradle on M1 (raised 2 studs)"},["M1","M3"],MECH,
     "Recolour heads/accents per palette; replace donor 7L rear axle with length ending in gearbox joiner."),
 mod("M5","Front axle: double wishbones, portal hubs, shocks","adapt","42039-1.mpd '42039 - frontaxle.ldr' (84) + '42039 - frontaxletop.ldr' (21)",
     ["independent suspension"],105,"donor transform",{"x":[-274,274],"y":[-189,-20],"z":[-116,330]},
     {"pairs_with":"M6 rack (donor pairing preserved)","mounts":"front frame rails (15L beams in frontaxle) -> M1"},["M1"],MECH,
     "Replace spring meshes with 73129; re-pose arms to lower front wheel centre by 8 LDU if the linkage allows."),
 mod("M6","Steering: rack, pinion extension, HOG, steering wheel","adapt + redesign","42039 '42039 - steeringrack.ldr' (22) + new HOG/column",
     ["rack steering","HOG knob","steering wheel"],42,"donor transform (rack) / car frame (new)",{"x":[-120,120],"y":[-200,-60],"z":[-80,200]},
     {"shafts":[{"id":"S4a","axis":"Y","x":0,"z":-60,"role":"HOG vertical shaft -> bevel pair -> pinion axle"},
                {"id":"S4b","axis":"Z","x":0,"y":-100,"role":"longitudinal steering shaft z 60->150"},
                {"id":"S4c","role":"transfer gears x 0->80 at z~150 then UJ column to wheel (80,-190,170)"}]},["M5","M1"],MECH),
 mod("M7","Cockpit: 2 seats, dashboard, console with shift lever","adapt","42039 '42039 - seat.ldr' x2 (12 each) + new dashboard/console",[],40,
     "car frame",{"x":[-160,160],"y":[-270,-60],"z":[120,380]},{"shift_lever":"drives S3","mounts":"seat rails on M1"},["M1","M3","M6"],TECH,
     "Seats recoloured black."),
 mod("M8","Butterfly doors x2","redesign (idea: 42039 doorlift hinge, skin like 42099 door1)","42039 doorlift/doorlift2; 42099 door1",["2 opening doors"],60,
     "per-door hinge frame at A-pillar hoop",{"x":[-290,290],"y":[-260,-50],"z":[100,410]},{"hinge":"M1 door hoop z~90, y~-210"},["M1","M9"],TECH+["render doors-open pose"]),
 mod("M9","Body panels: nose, wings, flanks, roof, screen frame, engine cover slats","redesign","own design",[],250,
     "car frame",{"x":[-290,290],"y":[-275,-30],"z":[-250,970]},{"mounts":"M1 sill rails, hoops, rear subframe"},["M1","M5","M2"],TECH),
 mod("M10","Front & rear ends: light bars, splitter, diffuser, exhausts","redesign","own design",[],70,"car frame",
     {"x":[-290,290],"y":[-190,-15],"z":[-260,975]},{"mounts":"M9 nose / M1 rear subframe"},["M9"],TECH),
 mod("M11","Rear wing on swan-neck supports","adapt (blade pattern 42093 spoiler, widened)","42093-1.mpd '42093 - spoiler.ldr' (11)",["rear wing"],30,
     "car frame",{"x":[-235,235],"y":[-320,-180],"z":[880,970]},{"mounts":"two supports into M1 rear subframe x=+-60"},["M1","M9"],TECH),
 mod("M12","Wheels x4","reuse","42039 wheel placements (15038 + 44771)",[],8,"donor transform",{"x":[-274,274],"y":[-172,0],"z":[-86,826]},
     {"hubs":"M5 portal hubs / M2 rear hubs (donor pairing)"},["M2","M5"],["vehicle stance script: ground contact, symmetry, transverse axes"]),
]
json.dump({"version":1,"frame":layout["frame"],"analytical_mechanism_verification":"deferred","budget_total":sum(m["parts_budget"] for m in modules),
           "modules":modules}, open('output/modules.json','w'), indent=1)
print('budget', sum(m["parts_budget"] for m in modules))
n=open('output/NOTES.md').read()
n=n.replace("- [ ] Phase 2 plan","""- [x] Phase 2 plan: design-brief.md (Fiamma V8), layout.json (measured), modules.json (M1-M12 contracts, budget ~911),
      rough placement prospect/rough/rough-layout.mpd -> render right/top/home OPENED (front/back rendered, not opened).
      Key measurements: tyre R=86.118 (installed geometry), donor->car translate (0,20,60), wheelbase 740, track 459,
      engine raised 40 + forward 20 (crank y=-100), gearbox in-line z 570-710 (ring shaft y=-60 = diff pinion, lay y=-100 = crank),
      42112 ratios 16:16 and 20:12. OPEN: front tyres float 8 LDU (fix in M5 or 0.62 deg rake).
      -> WAITING AT CHECKPOINT 2 for user""")
open('output/NOTES.md','w').write(n)
