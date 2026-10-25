import subprocess,json
for p in ['35480','14769','4032a','3941','50450','6141','4589','3957a','15068','4081b','3070b','3069b','98138']:
    o=subprocess.run(['./ldraw-agent','part',p],capture_output=True,text=True).stdout
    try:
        d=json.loads(o); print(p,d['metadata']['description'],{k:v for k,v in d.items() if 'bound' in k or 'bbox' in k})
    except Exception as e: print(p,'err',o[:200])