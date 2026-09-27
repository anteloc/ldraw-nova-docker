"""Cobalt Courier motorbike. Adapted measured atlas frame/fairing and rim positions;
new blue courier livery, topped cargo box and front-facing clear lamp.
Run from repository root: .venv/bin/python output/generators/cobalt-courier.py
"""
import json
from pathlib import Path
out=Path('output')
p=json.loads(Path('examples/vehicle-atlas/touring-motorcycle/scene.plan.json').read_text())
p['author']='LDraw Astra assistant; measured motorcycle frame and wheel placements adapted from ldraw-astra vehicle examples'
s=p['sections'][0];s['name']='cobalt-courier.ldr'
s['description']='Cobalt Courier small touring motorcycle; front -Z, ground Y=0; cargo box is fixed'
steps=s['steps'];step0,step1,step2=steps
for v in step0:
 if v['id']=='vintage-fairing':v['colour']='@colours.Medium_Azure'
# Front stud on fairing is at local (0,-16,-97.5): world (0,-80.414,-47.5).
# Upright round plate rotated about X, underside 8 LDU behind its front-facing stud plane.
step2.insert(0,{'id':'front-clear-lamp','ref':'6141.dat','colour':'@colours.Trans_Clear','at':[0,-80.414,-55.5], 'matrix':[[1,0,0],[0,0,-1],[0,1,0]],'purpose':'clear round headlamp on native forward-facing fairing stud'})
step2=[v for v in step2 if v['id']!='rack-pad']
step2.extend([
 {'id':'cargo-base','ref':'3023b.dat','colour':'@colours.Dark_Bluish_Grey','at':[0,-80.414,50], 'yaw':90,'purpose':'low 1x2 dispatch bag base on rear rack studs'},
 {'id':'cargo-lid','ref':'3069b.dat','colour':'@colours.Yellow','at':[0,-88.414,50], 'yaw':90,'purpose':'contrasting flush case lid'},
])
s['steps'][2]=step2
(out/'cobalt-courier.plan.json').write_text(json.dumps(p,indent=2)+'\n')
print('wrote',out/'cobalt-courier.plan.json')
