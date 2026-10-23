import json
v=json.load(open('output/nightfang/review/validation.json'))
for d in v['diagnostics']:
    if d['code']=='assembly.body_overlap': print(d)