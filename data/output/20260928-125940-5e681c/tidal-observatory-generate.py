"""Original Tidal Observatory. Generate modular plans; serialize with ldraw-agent build."""
from pathlib import Path
import json

OUT = Path(__file__).resolve().parent
AUTHOR = 'OpenAI - original Tidal Observatory design'
TAN, STONE, WHITE, ROOF, DARK, BLUE, WOOD, GOLD = 19, 28, 15, 378, 72, 272, 70, 297
sections = []


def p(id, ref, c, xyz=None, **kw):
    return dict(id=id, ref=ref if '.' in ref else ref+'.dat', colour=c,
                **({'at':xyz} if xyz is not None else {}), purpose=id.replace('-', ' '), **kw)


def sec(name, desc, steps, anchors=None):
    s=dict(name='tidal-'+name+'.ldr',description=desc,steps=[s for s in steps if s])
    if anchors:s['anchors']=anchors
    sections.append(s)
    return s


PLATES={(1,1):'3024',(2,1):'3023b',(4,1):'3710',(6,1):'3666',(8,1):'3460',
        (2,2):'3022',(4,2):'3020',(6,2):'3795',(8,2):'3034',
        (4,4):'3031',(8,4):'3035',(8,6):'3036',(6,6):'3958',(12,4):'3029',(12,6):'3028'}
BRICKS={1:'3005',2:'3004',3:'3622',4:'3010',6:'3009',8:'3008'}


def rect(x0,z0,w,d,y,c,label,kind='plate'):
    cells={(x,z) for x in range(w) for z in range(d)}
    result=[]; n=0
    choices=[]
    if kind=='plate':
        for (a,b),ref in PLATES.items():
            choices.extend([(a,b,ref,0),(b,a,ref,90)])
    elif kind=='brick':
        for a,ref in [(2,'3003'),(4,'3001'),(6,'2456'),(8,'3007')]:
            choices.extend([(a,2,ref,0),(2,a,ref,90)])
        for a,ref in BRICKS.items():choices.extend([(a,1,ref,0),(1,a,ref,90)])
    choices.sort(key=lambda q:q[0]*q[1],reverse=True)
    while cells:
        xx,zz=min(cells,key=lambda q:(q[1],q[0]))
        for a,b,ref,yaw in choices:
            take={(xx+i,zz+j) for i in range(a) for j in range(b)}
            if take<=cells:
                result.append(p(f'{label}-{n}',ref,c,[x0+20*xx+10*a,y,z0+20*zz+10*b],yaw=yaw))
                n+=1;cells-=take;break
        else:raise ValueError('Cannot tile rectangle')
    return result


def deck(w,d):
    # Cross-bond the upper deck against the lower deck's large-plate seams.
    lower=rect(-10*w,-10*d,w,d,8,DARK,'deck-under')
    upper=[]
    xs=[2,w-4,2] if w>8 else [w]
    zs=[2,d-4,2] if d>8 else [d]
    x=-10*w
    for i,a in enumerate(xs):
        z=-10*d
        for j,b in enumerate(zs):
            upper+=rect(x,z,a,b,0,STONE,f'deck-top-{i}-{j}');z+=20*b
        x+=20*a
    return [lower,upper]


def line_cells(cells,y,c,label):
    cells=set(cells); out=[];n=0
    while cells:
        x,z=min(cells,key=lambda q:(q[1],q[0]))
        options=[]
        for length in [8,6,4,3,2,1]:
            for dx,dz,yaw in [(20,0,0),(0,20,90)]:
                run={(x+dx*i,z+dz*i) for i in range(length)}
                if run<=cells:options.append((length,dx,dz,yaw,run))
        length,dx,dz,yaw,run=max(options,key=lambda q:q[0])
        # Offset alternate masonry courses while preserving openings and corner bonds.
        if int(abs(y)//24)%2 and length>=4 and n%3==0:
            length=2;run={(x+dx*i,z+dz*i) for i in range(length)}
        out.append(p(f'{label}-{n}',BRICKS[length],c,[x+dx*(length-1)/2,y,z+dz*(length-1)/2],yaw=yaw))
        cells-=run;n+=1
    return out


def rim(w,d,y,c,label,project=False):
    # Side rails exclude front/back corners, avoiding coincident cornice pieces.
    ext=20 if project else 0
    out=rect(-w*10-ext,-d*10-ext,w+(2 if project else 0),2 if project else 1,y,c,label+'-f')
    out+=rect(-w*10-ext,d*10-20,w+(2 if project else 0),2 if project else 1,y,c,label+'-b')
    out+=rect(-w*10-ext,-d*10+20,2 if project else 1,d-2,y,c,label+'-l')
    out+=rect(w*10-20,-d*10+20,2 if project else 1,d-2,y,c,label+'-r')
    return out


def bay(tall=False,door=False):
    height=144 if tall else 72
    st=[[p('sill','3795',WHITE,[0,-8,-10])]]
    pieces=[]
    for side in [-1,1]:
        for row in range(height//24):pieces.append(p(f'pier-{side}-{row}','3005',TAN,[50*side,-32-24*row,0]))
    pieces.append(p('frame','60596' if tall else '60594',BLUE,[0,-8-height,0]))
    if door:pieces.append(p('door','60623',BLUE,[-32,-8-height,5]))
    elif tall:pieces.append(p('glass','57895',47,[0,-3-height,5]))
    else:
        pieces.extend([p('pane-left','60608',47,[-32,-76,4],yaw=-90),p('pane-right','60608',47,[32,-76,4],yaw=90)])
    st.append(pieces)
    st.append([p('arch','3307',TAN,[0,-height-56,0])])
    return sec('door-bay' if door else 'tall-bay' if tall else 'short-bay','Recessed blue glazing, limestone arch and projecting white sill',st)


bay(True);bay(False);bay(True,True)
sec('slit-window','Two two-stud frames stacked with matching panes',[[p('frame','60592',BLUE,[0,-48,0]),p('glass','60601',47,[0,-48,0]),p('frame-upper','60592',BLUE,[0,-96,0]),p('glass-upper','60601',47,[0,-96,0])]])

# Furniture and terrace fittings have bottom support plane Y=0.
sec('bookcase','Marine archive with three shelves and individually colored volumes',[
 [p(f'leg-{x}-{i}','3005',WOOD,[x,-24-32*i,0]) for x in [-50,50] for i in range(3)],
 [p(f'shelf-{i}','3666',WOOD,[0,-32-32*i,0]) for i in range(3)],
 [p(f'volume-{i}-{j}','3005',[272,378,28,70,19][(i+j)%5],[-30+20*j,-24-32*i,0]) for i in range(3) for j in range(4)]])
sec('chart-table','Nautical chart desk with brass lamp',[
 [p(f'leg-{x}-{z}','3005',WOOD,[x,-24,z]) for x in [-50,50] for z in [-10,10]],
 [p('tabletop','3795',WOOD,[0,-32,0])],
 [p('nautical-chart','3068bp32',19,[-20,-40,0]),p('inkwell','6141',0,[30,-40,10]),p('lamp-foot','6141',GOLD,[50,-40,-10]),p('lamp-stem','3062b',GOLD,[50,-64,-10]),p('lamp-shade','4740',378,[50,-72,-10])]])
sec('bench','Teak harbor bench with backrest',[
 [p('leg-left','3004',0,[-50,-24,0],yaw=90),p('leg-right','3004',0,[50,-24,0],yaw=90)],
 [p('seat','3795',WOOD,[0,-32,0])],
 [p('back-l','4865b',WOOD,[-40,-56,10]),p('back-m','4865b',WOOD,[0,-56,10]),p('back-r','4865b',WOOD,[40,-56,10])]])
sec('planter','Stone coastal planter with layered windswept leaves and pale flowers',[
 [p('foot','3031',DARK,[0,-8,0]),p('soil','3003',STONE,[-20,-32,0]),p('soil-r','3003',STONE,[20,-32,0]),p('cap','3031',TAN,[0,-40,0])],
 [p('trunk','3062b',WOOD,[-10,-64,10]),p('leaves-low','2423',288,[-10,-72,10],yaw=-30),p('leaves-high','2423',2,[-10,-80,10],yaw=140),p('flower-a','24866',15,[-10,-88,10]),p('flower-b','24866',25,[10,-48,-10])]])
sec('lamp','Slender brass-collared quay light with an amber lantern',[
 [p('base','3022',0,[0,-8,0]),p('jumper','3794b',0,[0,-16,-10])],
 [p(f'post-{i}','3062b',0,[0,-40-24*i,-10]) for i in range(4)],
 [p('collar','6141',GOLD,[0,-120,-10]),p('light','3062b',46,[0,-144,-10]),p('shade','4740',0,[0,-152,-10]),p('finial','4589',0,[0,-176,-10])]])
sec('instrument','Static brass telescope on a pedestal with a dark-blue objective lens',[
 [p('plinth','3022',WHITE,[0,-8,0]),p('shaft','3003',TAN,[0,-32,0]),p('shaft2','3003',TAN,[0,-56,0]),p('mount','4733',GOLD,[10,-80,10]),p('mount-cap','3070b',GOLD,[10,-88,10])],
 [p(f'telescope-tube-{i}','3062b',GOLD,[10,-70,-24-24*i],matrix=[[1,0,0],[0,0,-1],[0,1,0]]) for i in range(3)],
 [p('objective','98138',41,[10,-70,-80],matrix=[[1,0,0],[0,0,-1],[0,1,0]])]])



def hall(name,ground):
    st=deck(28,20);nrows=8 if ground else 6
    for row in range(nrows):
        cells=set()
        for x in range(-270,271,20):
            frontblocked=any(abs(x-b)<60 for b in [-180,0,180]) and (ground or row>=1)
            if not frontblocked:cells.add((x,-190))
            if row==0 or abs(x)>=210:cells.add((x,190))
        for z in range(-170,171,20):
            for x in [-270,270]:
                blocked=any(abs(z-b)<20 for b in [-100,60]) and 1<=row<=4
                if not blocked:cells.add((x,z))
        st.append(line_cells(cells,-24*(row+1),TAN if row else STONE,f'wall-{row}'))
    feats=[]
    for x in [-180,0,180]:
        feats.append(p(f'facade-{x}','tidal-door-bay.ldr' if ground and x==0 else 'tidal-tall-bay.ldr' if ground else 'tidal-short-bay.ldr',19,[x,0 if ground else -24,-190]))
    for x in [-270,270]:
        for z in [-100,60]:feats.append(p(f'side-window-{x}-{z}','tidal-slit-window.ldr',19,[x,-24,z],yaw=90 if x<0 else -90))
    st.append(feats)
    y=-200 if ground else -152
    # The bay arch replaces the first front cornice course in its reserved cells.
    pieces=rim(28,20,y,WHITE,'shim')
    pieces=[q for q in pieces if not q['id'].startswith('shim-f')]
    for x in range(-270,271,20):
        if not any(abs(x-b)<60 for b in [-180,0,180]):pieces.append(p(f'shim-front-{x}','3024',WHITE,[x,y,-190]))
    st.append(pieces)
    st.append(rim(28,20,y-8,WHITE,'band'))
    st.append(rim(28,20,y-16,WHITE,'projected',True))
    # Small pilaster capitals, kept beneath the cornice outside the glazing.
    st.append([p(f'front-capital-{x}','3020',WHITE,[x,y-8,-200]) for x in []])
    if ground:
        furniture=[p('west-chart-desk','tidal-chart-table.ldr',WOOD,[-140,0,0]),p('east-chart-desk','tidal-chart-table.ldr',WOOD,[140,0,0]),p('west-chair','4079',BLUE,[-140,-8,60]),p('east-chair','4079',BLUE,[140,-8,60]),p('archive','tidal-bookcase.ldr',WOOD,[-140,0,150]),p('specimen','tidal-instrument.ldr',WHITE,[120,0,140])]
    else:
        furniture=[p('archive-west','tidal-bookcase.ldr',WOOD,[-180,0,150]),p('archive-middle','tidal-bookcase.ldr',WOOD,[-20,0,150]),p('reading-desk','tidal-chart-table.ldr',WOOD,[-80,0,-20]),p('reading-chair','4079',BLUE,[-80,-8,40]),p('observation-dais','tidal-instrument.ldr',WHITE,[140,0,60])]
    # Tile only the free floor; actual furniture sockets retain exposed stud footprints.
    occupied=set()
    for f in furniture:
        x,_,z=f['at'];ref=f['ref']
        if 'chart-table' in ref: w,d=6,2
        elif 'bookcase' in ref:w,d=6,1
        elif ref=='4079.dat':w,d=2,4
        else:w,d=2,2
        occupied.update((xx,zz) for xx in range(-250,251,20) for zz in range(-170,171,20)
                        if abs(xx-x)<w*10 and abs(zz-z)<d*10)
    floor_tiles=[]
    for xx in range(-250,251,20):
        for zz in range(-170,171,20):
            if (xx,zz) in occupied:continue
            c=28 if abs(xx)>=230 or abs(zz)>=150 else 19
            if abs(xx)<50 and -150<=zz<=130:c=272 if abs(xx)==30 else 378
            floor_tiles.append(p(f'inlaid-floor-{xx}-{zz}','3070b',c,[xx,-8,zz]))
    st.append(floor_tiles)
    st.append(furniture)
    if ground:
        st.append(rect(-80,-240,8,2,8,WHITE,'porch-under'))
        st.append(rect(-80,-240,8,2,0,WHITE,'porch-top'))
        for row in range(7):
            st.append([p(f'porch-pillar-{x}-{row}','3005',WHITE,[x,-24*(row+1),-230]) for x in [-70,70]])
        st.append(rect(-80,-240,8,2,-176,WHITE,'porch-entablature'))
        st.append([p('porch-fascia','3008',TAN,[0,-200,-230])])
        st.append(rect(-80,-240,8,2,-208,WHITE,'porch-cap'))
    sec(name,'Furnished limestone '+('marine chart hall' if ground else 'upper archive and reading room')+' with broad rear exhibit cutaway',st,{'base':{'at':[0,16,0]},'next':{'at':[0,y-16,0]}})


hall('ground-hall',True);hall('upper-hall',False)


def tower(name,rows):
    st=deck(10,12)
    for row in range(rows):
        cells=set()
        for x in range(-90,91,20):
            if not (abs(x)<20 and 1<=row<=4):cells.add((x,-110))
            if row==0 or abs(x)>=50:cells.add((x,110))
        for z in range(-90,91,20):
            for x in [-90,90]:
                if not (abs(z)<20 and 1<=row<=4):cells.add((x,z))
        st.append(line_cells(cells,-24*(row+1),STONE if row==0 else TAN,f'towerwall-{row}'))
    st.append([p('front-slit','tidal-slit-window.ldr',BLUE,[0,-24,-110]),p('east-slit','tidal-slit-window.ldr',BLUE,[90,-24,0],yaw=-90),p('west-slit','tidal-slit-window.ldr',BLUE,[-90,-24,0],yaw=90)])
    y=-24*rows
    for offset in [8,16,24]:st.append(rim(10,12,y-offset,WHITE,f'cornice-{offset}',offset==24))
    sec(name,'Offset lantern tower masonry stage with glazed slits and open rear',st,{'base':{'at':[0,16,0]},'next':{'at':[0,y-24,0]}})


tower('tower-base',8);tower('tower-middle',6)

# Balcony collar above the main roofs, deliberately airy rather than a heavy third storey.
st=deck(10,12)
st[1]=[q for q in st[1] if not any(q['id'].startswith(f'deck-top-{i}-0-') for i in range(3))]
st[1]+=rect(-100,-160,10,4,0,STONE,'clock-cantilever-deck')
for row in range(3):
    cells={(x,z) for x in range(-90,91,20) for z in [-110,110]}|{(x,z) for x in [-90,90] for z in range(-90,91,20)}
    st.append(line_cells(cells,-24*(row+1),TAN,f'collarwall-{row}'))
st.append(rim(10,12,-80,WHITE,'collar-rim',True))
st.append(rect(-120,-140,12,14,-88,WHITE,'balcony-floor'))
st.append([p('clock-left','3003p0b',TAN,[-20,-56,-140]),p('clock-right','3003p0b',TAN,[20,-56,-140])])
# Clock housings receive an actual ledge under their two rows of sockets.
st.append([p('clock-shelf','3020',WHITE,[0,-32,-140]),p('clock-back-support','3001',TAN,[0,-24,-140])])
sec('tower-collar','Projected lantern balcony and twin tide/time dials',st,{'base':{'at':[0,16,0]},'next':{'at':[0,-88,0]}})

# Four-sided glazed lantern: each side leaves one-stud corner pillars.
st=deck(8,8)
for row in range(6):
    st.append([p(f'corner-{row}-{x}-{z}','3005',0,[x,-24*(row+1),z]) for x in [-70,70] for z in [-70,70]])
    forside=[]
    for z in [-70,70]:
        for x in [-50,50]:forside.append(p(f'edge-{row}-{x}-{z}','3005',0,[x,-24*(row+1),z]))
    for x in [-70,70]:
        for z in [-50,50]:forside.append(p(f'edge-{row}-{x}-{z}','3005',0,[x,-24*(row+1),z]))
    st.append(forside)
windows=[]
for i,(x,z,yaw) in enumerate([(0,-70,0),(0,70,180),(-70,0,90),(70,0,-90)]):
    windows.append(p(f'frame-{i}','60596',0,[x,-144,z],yaw=yaw))
    # Rigidly transform the pane's offset along the local rear axis.
    dx,dz={0:(0,5),180:(0,-5),90:(5,0),-90:(-5,0)}[yaw]
    windows.append(p(f'glass-{i}','57895',47,[x+dx,-139,z+dz],yaw=yaw))
st.append(windows)
st.append([p('beacon-base','3031',0,[0,-8,0]),p('beacon-pedestal','3003',GOLD,[0,-32,0]),p('beacon-core','3003',46,[0,-56,0]),p('beacon-upper','3003',46,[0,-80,0]),p('beacon-cap','3022',GOLD,[0,-88,0])])
st.append(rim(8,8,-152,0,'lantern-lintel'))
sec('lantern','Four glazed sides around a warm amber weather beacon',st,{'base':{'at':[0,16,0]},'next':{'at':[0,-152,0]}})

# Supported hipped roof, with no stretched slopes.
st=deck(10,10)
for tier in range(4):
    width=10-2*tier; edge=width*10-10;y=-24*(tier+1)
    st.append(rect(-edge+10,-edge+10,width-2,width-2,y,0,f'cap-core-{tier}','brick'))
    perimeter=[]
    high=edge-20
    for x in range(-edge+50,edge-30,40):
        perimeter.append(p(f'cap-f-{tier}-{x}','3039',BLUE,[x,y,-high]))
        perimeter.append(p(f'cap-b-{tier}-{x}','3039',BLUE,[x,y,high],yaw=180))
    for z in range(-edge+50,edge-30,40):
        perimeter.append(p(f'cap-l-{tier}-{z}','3039',BLUE,[-high,y,z],yaw=90))
        perimeter.append(p(f'cap-r-{tier}-{z}','3039',BLUE,[high,y,z],yaw=-90))
    for yaw,x,z in [(0,high,-high),(90,-high,-high),(180,-high,high),(270,high,high)]:
        perimeter.append(p(f'hip-corner-{tier}-{yaw}','3045',BLUE,[x,y,z],yaw=yaw))
    # Core cells under the perimeter would clash; use only a narrowed square core below.
    st[-1]=rect(-edge+30,-edge+30,width-4,width-4,y,0,f'cap-core-{tier}','brick') if width>4 else []
    st.append(perimeter)
st.append([p('finial-plate','3022',GOLD,[0,-104,0]),p('finial-jumper','3794b',GOLD,[0,-112,-10]),p('finial','4589',GOLD,[0,-136,-10])])
sec('lantern-roof','Dark-blue hipped cap and brass finial',st,{'base':{'at':[0,16,0]}})

# Dome: outer curved skirt, circular raised collar, then a smooth four-quarter cap.
st=deck(28,20)
for row in range(2):
    # A solid octagonal drum provides ordinary underside stud support.
    for z,w in [(-120,8),(-80,12),(-40,14),(0,14),(40,12),(80,8)]:
        st.append(rect(-w*10,z,w,2,-24*(row+1),WHITE if row==1 else TAN,f'drum-{row}-{z}','brick'))
for yaw in [0,90,180,270]:
    st.append([p(f'copper-skirt-{yaw}','87559',ROOF,[0,-96,0],yaw=yaw),p(f'raised-collar-{yaw}','48092',ROOF,[0,-120,0],yaw=yaw)])
# Interior core carries the small crown independently of the thin circular collar.
for row in range(3):st.append(rect(-40,-40,4,4,-72-24*row,ROOF,f'dome-core-{row}','brick'))
# Crown bottom -144; it sits on the core top -144 and above the outer collar.
for yaw,(x,z) in [(0,(10,-10)),(90,(-10,-10)),(180,(-10,10)),(270,(10,10))]:
    st.append([p(f'crown-{yaw}','88293',ROOF,[x,-168,z],yaw=yaw)])
st.append([p('crown-cap','3022',GOLD,[0,-176,0]),p('crown-jumper','3794b',GOLD,[0,-184,-10]),p('crown-finial','4589',GOLD,[0,-208,-10])])
# Reserve a quiet tiled roof terrace around the observatory drum.
tiles=[]
for x in range(-250,251,20):
    for z in range(-170,171,20):
        if (abs(x)<=150 and abs(z)<=130) or (abs(x+220)<20 and abs(z-40)<20):continue
        tiles.append(p(f'roof-paving-{x}-{z}','3070b',DARK,[x,-8,z]))
st.append(tiles)
st.append([p('roof-telescope','tidal-instrument.ldr',GOLD,[-220,0,40])])
st.append(rim(28,20,-8,WHITE,'roof-rim'))
sec('dome-roof','Patinated round observatory dome above an octagonal masonry drum and quiet roof terrace',st,{'base':{'at':[0,16,0]}})

# Harbor base: two bonded plate layers and solid raised quay.
st=[]
st.append(rect(-480,-400,48,40,8,DARK,'sea-under'))
cross=[]
for zi,(z,d) in enumerate([(-400,2),(-360,36),(360,2)]):
    for xi,(x,w) in enumerate([(-480,2),(-440,44),(440,2)]):
        cross+=rect(x,z,w,d,0,272,f'sea-cross-{zi}-{xi}')
st.append(cross)
st.append(rect(-480,-280,48,34,-24,DARK,'quay-core','brick'))
st.append(rect(-480,-280,48,34,-32,71,'quay-deck'))
sea=[]
for x in range(-460,461,40):
    for z in [-380,-340,-300]:
        sea.append(p(f'sea-tile-{x}-{z}','3068b',23 if (x//40+z//40)%11==0 else 272,[x,-8,z]))
st.append(sea)
# Paving excludes real module footprints and fixture anchors.
fixtures=[(-400,-200,4,4,'planter'),(360,-220,4,4,'planter'),(-400,360,4,4,'planter'),(-260,-220,2,2,'lamp'),(240,-220,2,2,'lamp'),(280,300,6,2,'bench')]
paving=[]
for x in range(-460,461,40):
    for z in range(-260,381,40):
        hallfoot=-400<=x<160 and -120<=z<280
        towerfoot=190<x<420 and -40<z<240
        stairfoot=-200<=x<-40 and -200<=z<-120
        parapet=(z==-260 and (x<=-260 or x>=-20))
        fixture=any(abs(x-fx)<w*10+20 and abs(z-fz)<d*10+20 for fx,fz,w,d,_ in fixtures)
        if hallfoot or towerfoot or stairfoot or fixture or parapet:continue
        paving.append(p(f'paving-{x}-{z}','3068b',19 if (x//40+z//40)%4 else 28,[x,-40,z]))
st.append(paving)
# Broad shallow front steps, with the rear threshold reaching the raised hall deck.
for tier,(depth,y) in enumerate([(2,-40),(1,-48)]):st.append(rect(-200,-160-20*depth,8,depth,y,WHITE,f'entrance-step-{tier}'))
st.append([p(f'fixture-{i}','tidal-'+typ+'.ldr',19,[x,-32,z]) for i,(x,z,w,d,typ) in enumerate(fixtures)])
# Low quay parapets: gaps preserve the stairs and foreground story.
for i,(x0,w) in enumerate([(-460,10),(-20,22)]):
    st.append(rect(x0,-280,w,1,-56,TAN,f'sea-wall-{i}','brick'))
    st.append(rect(x0,-280,w,1,-64,WHITE,f'sea-wall-cap-{i}'))
sec('quay','Bonded marine base, tiled water, broad quay, entrance steps, planted terrace and harbor lamps',st)

root=[
 [p('quay','tidal-quay.ldr',19,[0,0,0])],
 [p('hall-ground','tidal-ground-hall.ldr',19,[-120,-48,80]),p('hall-upper','tidal-upper-hall.ldr',19,attach={'to':'hall-ground','anchor':'next','using':'base'}),p('observatory-roof','tidal-dome-roof.ldr',19,attach={'to':'hall-upper','anchor':'next','using':'base'})],
 [p('tower-base','tidal-tower-base.ldr',19,[300,-48,100]),p('tower-middle','tidal-tower-middle.ldr',19,attach={'to':'tower-base','anchor':'next','using':'base'}),p('tower-collar','tidal-tower-collar.ldr',19,attach={'to':'tower-middle','anchor':'next','using':'base'}),p('lantern','tidal-lantern.ldr',19,attach={'to':'tower-collar','anchor':'next','using':'base'}),p('lantern-roof','tidal-lantern-roof.ldr',19,attach={'to':'lantern','anchor':'next','using':'base'})]
]
main=dict(name='tidal-observatory.ldr',description='The Tidal Observatory - limestone marine institute, copper dome and weather lantern on a harbor quay',steps=root)
plan=dict(version=1,author=AUTHOR,sections=[main]+sections)
(OUT/'tidal-observatory.plan.json').write_text(json.dumps(plan,indent=2)+'\n')
# Isolated local tests use the same generated sections and normal builder.
for name in ['tall-bay','short-bay','dome-roof']:
    target=next(s for s in sections if s['name']=='tidal-'+name+'.ldr')
    test=dict(version=1,author=AUTHOR,sections=[dict(name='test-'+name+'.ldr',description='Local detail review',steps=[[p('test',target['name'],19,[0,0,0])]]),target])
    if name=='dome-roof':test['sections'].append(next(q for q in sections if q['name']=='tidal-instrument.ldr'))
    (OUT/f'tidal-{name}.plan.json').write_text(json.dumps(test,indent=2)+'\n')
print(OUT/'tidal-observatory.plan.json')
