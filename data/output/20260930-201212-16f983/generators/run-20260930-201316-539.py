import json
d=json.load(open('output/discovery/models-supercar.json'))
for r in d['results']:
    inv=r.get('inventory',{})
    print(r['score'], r['model'], '|', r['source_section'], '|', inv.get('physical_placements'), '|', r['description'][:150])
print(d['filters'])