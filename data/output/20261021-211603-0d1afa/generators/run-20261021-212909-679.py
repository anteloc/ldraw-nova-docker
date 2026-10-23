import subprocess,json
r=subprocess.run(['./ldraw-agent','inspect','output/nightfang/review/model.mpd','--contacts','all','--limit','200'],capture_output=True,text=True)
d=json.loads(r.stdout); g=d['geometry']
print(g.keys())
for k in g:
    if 'group' in k or 'component' in k or 'contact' in k or 'connect' in k:
        print(k, json.dumps(g[k])[:3000])
inst={i['index']:(i['part'],i['position'],i['section']) for i in g['instances']}