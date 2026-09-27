import json
p=json.load(open('examples/vehicle-atlas/grand-tourer/scene.plan.json'))
for s in p['sections']:
 print('\n',s['name'],len(s['steps'][0]));print(' '.join(f"{v['ref']}@{v.get('at')}" for v in s['steps'][0][-25:]))
