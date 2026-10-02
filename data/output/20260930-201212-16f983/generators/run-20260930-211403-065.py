import subprocess, json, re
from pathlib import Path
out=Path('output/phase3/donor'); out.mkdir(parents=True,exist_ok=True)
r=subprocess.run(['./ldraw-agent','extract','data/models-annotated/42039-1.mpd','--section','42039 - 24 Hours Race Car.ldr','--namespace','d39','--output',str(out/'d39-full.mpd'),'--normalize-rotations','--repair-bfc-comments','--force'],capture_output=True,text=True)
d=json.loads(r.stdout) if r.stdout.strip().startswith('{') else {}
print('extract exit',r.returncode,d.get('root'))
root=d.get('root')
txt=(out/'d39-full.mpd').read_text(encoding='utf-8-sig').replace('\r\n','\n').split('\n')
# truncate root block after N steps
def cut(n, name):
    res=[];inroot=False;steps=0;skip=False
    for l in txt:
        f=l.split(None,2)
        if f[:2]==['0','FILE']:
            inroot=(f[2].strip()==root); skip=False
        if inroot:
            if skip: 
                if f[:2]==['0','NOFILE']: res.append(l)
                continue
            res.append(l)
            if f[:2] in (['0','STEP'],['0','ROTSTEP']):
                steps+=1
                if steps>=n: skip=True
        else: res.append(l)
    (out/name).write_text('\r\n'.join(res),encoding='utf-8')
cut(33,'d39-rolling-s33.mpd')
print((out/'d39-rolling-s33.mpd').stat().st_size)
