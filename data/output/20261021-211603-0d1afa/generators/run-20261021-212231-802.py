import subprocess,json
def b(p):
    r=subprocess.run(['./ldraw-agent','part',p,'--limit','0'],capture_output=True,text=True)
    try:
        d=json.loads(r.stdout); print(p,d['metadata']['description'],d['bounds']['min'],d['bounds']['max'],d['stud_positions'][:4])
    except Exception as e: print(p,'ERR',r.stdout[:100],r.stderr[:100])
for p in ['6141','2412b','3010','3004','3040b','3037','4286','3298','3297','3039','4287','3665','3034','3795','69729','87079','3023','3069b','3070b','2431','3710','3666','11477','15068','93273','4871','3938','30363','4081b','3043','6091','4730','3023','98138']: b(p)