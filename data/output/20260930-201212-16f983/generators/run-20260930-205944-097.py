import json, subprocess, re
from pathlib import Path
SL=[('m2-diff-8880','8880-1.mpd','8880 - step15.ldr','M2 diff+UJ (8880)'),
    ('m3-gbx-8880','8880-1.mpd','8880 - step13.ldr','M3 4-speed gearbox (8880)'),
    ('m3-gbx-42112','42112-1.mpd','42112 - gearshift.ldr','M3 gearshift (42112)'),
    ('m4-v8-42039','42039-1.mpd','42039 - motor.ldr','M4 V8 motor (42039)'),
    ('m4-v8-8880','8880-1.mpd','8880 - step27-1-5.ldr','M4 V8 block (8880)'),
    ('m5-fa-42039','42039-1.mpd','42039 - frontaxle.ldr','M5 front axle (42039)'),
    ('m5-fa-42096','42096-1.mpd','42096 - frontaxle.ldr','M5 front axle (42096)'),
    ('m6-rack-42039','42039-1.mpd','42039 - steeringrack.ldr','M6 rack (42039)'),
    ('m6-steer-42096','42096-1.mpd','42096 - steering.ldr','M6 steering (42096)'),
    ('m6-col-5767','5767-1.mpd','5767 - Steering shaft vertical.ldr','M6 column (5767)'),
    ('m7-seat-42039','42039-1.mpd','42039 - seat.ldr','M7 seat (42039)'),
    ('m8-doorlift-42039','42039-1.mpd','42039 - doorlift2.ldr','M8 door lift (42039)'),
    ('m8-door-42099','42099-1.mpd','42099 - door1.ldr','M8 door (42099)'),
    ('m11-spoiler-42096','42096-1.mpd','42096 - spoiler.ldr','M11 spoiler (42096)'),
    ('m11-spoiler-42093','42093-1.mpd','42093 - spoiler.ldr','M11 spoiler (42093)')]
out=Path('output/prospect/shortlist'); out.mkdir(parents=True, exist_ok=True)
res=[]
for ns,f,sec,label in SL:
    dst=out/f'{ns}.mpd'
    r=subprocess.run(['./ldraw-agent','extract',f'data/models-annotated/{f}','--section',sec,'--namespace',ns,
                      '--output',str(dst),'--normalize-rotations','--repair-bfc-comments','--force'],capture_output=True,text=True)
    try: d=json.loads(r.stdout)
    except Exception: d={}
    res.append(dict(ns=ns,file=f,section=sec,label=label,exit=r.returncode,root=d.get('root'),
                    diag={k:v for k,v in (d.get('diagnostic_counts') or {}).items()} if isinstance(d.get('diagnostic_counts'),dict) else None,
                    err=(r.stderr or '')[-200:] if r.returncode==2 else ''))
    print(ns, 'exit', r.returncode, d.get('root'), res[-1]['diag'], res[-1]['err'])
json.dump(res, open(out/'shortlist.json','w'), indent=1)