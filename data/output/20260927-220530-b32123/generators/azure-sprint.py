"""Generate Azure Sprint, an attributed adaptation of the LDraw Astra grand-tourer construction.
Run from toolkit repository root: .venv/bin/python output/generators/azure-sprint.py
"""
import json
from pathlib import Path
src=Path('examples/vehicle-atlas/grand-tourer/scene.plan.json')
out=Path('output')
p=json.loads(src.read_text())
p['author']='LDraw Astra assistant (Azure Sprint redesign); chassis and wheel geometry adapted from ldraw-astra vehicle examples'
name_map={s['name']:s['name'].replace('grand-tourer','azure-sprint') for s in p['sections']}
for s in p['sections']:
 old=s['name'];s['name']=name_map[old]
 s['description']=s['description'].replace('Grand tourer','Azure Sprint racing coupe').replace('grand tourer','racing coupe')
 for step in s['steps']:
  for v in step:
   v['ref']=name_map.get(v['ref'],v['ref'])
   c=v['colour'];v['colour']= {'@colours.Dark_Green':'@colours.Medium_Azure','@colours.Tan':'@colours.Black'}.get(c,c)
root=p['sections'][0]['steps'][0]
# body and front altered with white shoulders and a contrasting waistline
body=next(s for s in p['sections'] if s['name']=='azure-sprint-body.ldr')['steps'][0]
for v in body:
 x,y,z=v['at'];ref=v['ref']
 if ref=='3460.dat' and abs(x)==50: v['colour']='@colours.White' # side blade
 # These 2x4 deck plates under the bonnet must stay azure; the racing stripe is confined to the sculpted skin.
cabin=next(s for s in p['sections'] if s['name']=='azure-sprint-cabin.ldr')['steps'][0]
for v in cabin:
 x,y,z=v['at'];ref=v['ref']
 if ref=='50950.dat' and abs(x)==10 and z==-130: v['colour']='@colours.White' # two-stud bonnet stripe
 if ref=='93273.dat':v['colour']='@colours.Black' # quiet roof
 if ref=='3020.dat' and z in (-20,20):v['colour']='@colours.Dark_Bluish_Grey' # lighter recessed cockpit surround
 if ref=='6636.dat' and (abs(x)==50 or z==150): v['colour']='@colours.White' # shoulder pinstripe and rear racing marker
 if ref=='69729.dat' and z==-80: v['colour']='@colours.Medium_Azure'
 if ref=='69729.dat' and z in (80,120):v['colour']='@colours.Medium_Azure'
for v in root:
 if v['ref']=='69729.dat':v['colour']='@colours.Black' # front/rear bumper blades
# Front fascia has a black grille, deep metallic sill, two lamps; rear dark inset and scarlet lamps.
front=next(s for s in p['sections'] if s['name']=='azure-sprint-front.ldr')['steps'][0]
rear=next(s for s in p['sections'] if s['name']=='azure-sprint-rear.ldr')['steps'][0]
for v in front+rear:
 if v['ref']=='4070.dat' and abs(v['at'][0])<40:v['colour']='@colours.Black'
 if v['ref']=='3069b.dat':v['colour']='@colours.Black'
# No extra decoration is superposed on the axle, bonnet or glazing.
(out/'azure-sprint.plan.json').write_text(json.dumps(p,indent=2)+'\n')
print('Wrote',out/'azure-sprint.plan.json', 'sections',len(p['sections']))
