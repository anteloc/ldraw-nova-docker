import subprocess,json
def info(p,n=40,filt=None):
    r=subprocess.run(['./ldraw-agent','part',p,'--limit',str(n)],capture_output=True,text=True)
    d=json.loads(r.stdout)
    print('==',p,d['metadata']['description'],'bounds',d['bounds']['min'],d['bounds']['max'])
    for c in d['connectors']:
        print('  ',c['kind'],c['role'][:4],[round(x,1) for x in c['position']],'dir=',[round(x) for x in (c['frame'][1])])
for p in ['98282','6014b','6015','2437','50950','4079']: info(p,12)