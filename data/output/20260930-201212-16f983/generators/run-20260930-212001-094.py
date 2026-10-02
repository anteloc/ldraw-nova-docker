import json, collections
d=json.load(open('output/phase3/donor/donor-rear.inspect.json'))
for code in ['technic.invalid_transform','technic.invalid_seating','connection.invalid_transform']:
    x=[q for q in d['diagnostics'] if q['code']==code][:2]; print(json.dumps(x)[:700])
g=d['geometry']; print([k for k in g.keys()])
