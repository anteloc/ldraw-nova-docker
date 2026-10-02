import sys, json, re
sys.path.insert(0,'.')
import numpy as np
from pathlib import Path
from ldraw_tools.document import source_blocks
from ldraw_tools.common import normalized
out=Path('output/prospect/rough'); SL=Path('output/prospect/shortlist')
D=np.array([0,20,60])   # donor 42039 world -> car frame (road Y=0, front axle Z=0)
blocks=source_blocks('data/models-annotated/42039-1.mpd')
main=blocks[normalized('42039 - 24 Hours Race Car.ldr')]
steps=[[]]
for n,l in main:
    f=l.split()
    if f[:2] in (['0','STEP'],['0','ROTSTEP']): steps.append([])
    elif f and f[0]=='1': steps[-1].append(l)
rear=[l for s in steps[:7] for l in s]
wheels=[l for s in steps for l in s if re.search(r'\b(15038|44771)\.dat$',l.strip(),re.I)]
print('rear steps 1-7 lines',len(rear),'wheel lines',len(wheels), 'steps total', len(steps))
refs=sorted({' '.join(l.split()[14:]) for l in rear if not l.strip().lower().endswith('.dat')})
print('rear submodel refs', refs)
shock_root='rl-rshock-00-42039---shock-06_5L-hard-1.ldr'
def fix(l):
    f=l.split(None,14)
    if f[14].strip().lower()=='42039 - shock-06_5l-hard-1.ldr': f[14]=shock_root
    return ' '.join(f)
def T(ref,at,m=np.eye(3),col=16):
    return f"1 {col} {at[0]:g} {at[1]:g} {at[2]:g} "+' '.join(f'{v:g}' for v in np.asarray(m).flatten())+f" {ref}"
R90z=np.array([[0,-1,0],[1,0,0],[0,0,1]])
seat_m=np.array([[1,0,0],[0,0.992,0.122],[0,-0.122,0.992]])
root=['0 FILE rough-layout.ldr','0 Rough placement test (review only): wheels + unmodified donor units in planned car frame','0 Name: rough-layout.ldr','0 Author: LDraw Astra agent; donor sections keep their own headers','0 !LDRAW_ORG Model',
 T('rough-donor-rear-axle.ldr',D),
 T('m5-fa-42039-00-42039---frontaxle.ldr',np.array([0,-80,-60])+D),
 T('m6-rack-42039-00-42039---steeringrack.ldr',np.array([0,-80,0])+D),
 T('rl-ftop-00-42039---frontaxletop.ldr',np.array([0,-160,-80])+D),
 T('m4-v8-42039-00-42039---motor.ldr',np.array([0,-130,540])+D+np.array([0,-40,-20]),col=16),  # raised 40, forward 20
 T('m3-gbx-42112-00-42112---gearshift.ldr',[0,-80,700],R90z),
 T('m7-seat-42039-00-42039---seat.ldr',[80+110,-197.5,223.4],seat_m,col=0),
 T('m7-seat-42039-00-42039---seat.ldr',[-80+110,-197.5,223.4],seat_m,col=0),
 T('m11-spoiler-42093-00-42093---spoiler.ldr',[0,-300,930],col=0),
 '0 STEP']
for l in wheels:
    f=l.split(); x,y,z=map(float,f[2:5]); root.append(' '.join(f[:2]+[f'{x+D[0]:g}',f'{y+D[1]:g}',f'{z+D[2]:g}']+f[5:]))
root.append('0 NOFILE')
rear_sec=['0 FILE rough-donor-rear-axle.ldr','0 42039 main steps 1-7 (rear axle, diff, rear shocks) copied verbatim for review','0 Name: rough-donor-rear-axle.ldr','0 Author: copied from 42039-1.mpd (see its headers); wrapper by LDraw Astra agent','0 !LDRAW_ORG Model']+[fix(l) for l in rear]+['0 NOFILE']
body='\r\n'.join(root+rear_sec)+'\r\n'
for f in ['m5-fa-42039','m6-rack-42039','m4-v8-42039','m3-gbx-42112','m7-seat-42039','m11-spoiler-42093']:
    body+=(SL/f'{f}.mpd').read_text(encoding='utf-8-sig').replace('\r\n','\n').replace('\n','\r\n')
for f in ['rl-ftop','rl-rshock']:
    body+=(out/f'{f}.mpd').read_text(encoding='utf-8-sig').replace('\r\n','\n').replace('\n','\r\n')
Path(out/'rough-layout.mpd').write_text(body,encoding='utf-8',newline='')
print('written', len(body))
