import subprocess, json
from pathlib import Path
out=Path('output/phase3/donor')
txt=(out/'d39-full.mpd').read_text(encoding='utf-8-sig').replace('\r\n','\n').split('\n')
root='d39-00-42039---24-Hours-Race-Car.ldr'
res=[];inroot=False;steps=0;skip=False
for l in txt:
    f=l.split(None,2)
    if f[:2]==['0','FILE']: inroot=(f[2].strip()==root); skip=False
    if inroot:
        if skip:
            if f[:2]==['0','NOFILE']: res.append(l)
            continue
        res.append(l)
        if f[:2] in (['0','STEP'],['0','ROTSTEP']):
            steps+=1
            if steps>=21: skip=True
    else: res.append(l)
(out/'d39-rear-s21.mpd').write_text('\r\n'.join(res),encoding='utf-8')
r=subprocess.run(['./ldraw-agent','inspect',str(out/'d39-rear-s21.mpd'),'--contacts','all','--detail','full','--limit','400','--report',str(out/'d39-rear-s21.inspect.json')],capture_output=True,text=True)
print('exit',r.returncode, len(r.stdout))
d=json.load(open(out/'d39-rear-s21.inspect.json'))
print([k for k in d.keys()])
