import subprocess,json
def info(p):
    r=subprocess.run(['./ldraw-agent','part',p,'--limit','40'],capture_output=True,text=True)
    d=json.loads(r.stdout)
    print('==',p,d['metadata']['description'],'bounds',d['bounds']['min'],d['bounds']['max'])
    for c in d['connectors']:
        if c['kind'] in('stud','tube','socket','pin') or True:
            print('  ',c['kind'],c['role'],[round(x,1) for x in c['position']],'up=',[round(x) for x in (c['frame'][1])])
for p in ['4070','87087','99780','6157']: info(p)