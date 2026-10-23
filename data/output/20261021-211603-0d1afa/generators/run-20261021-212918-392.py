import subprocess,json
r=subprocess.run(['./ldraw-agent','inspect','output/nightfang/review/model.mpd','--contacts','all','--limit','200'],capture_output=True,text=True)
g=json.loads(r.stdout)['geometry']
inst={i['index']:(i['part'],[round(x) for x in i['position']]) for i in g['instances']}
for i in (117,118,119,120,134,18,23,33,34): print(i, inst[i])