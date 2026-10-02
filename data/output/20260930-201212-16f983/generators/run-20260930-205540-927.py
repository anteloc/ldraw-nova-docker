import json
R=json.load(open('output/prospect/census.json'))
car=[c for c in R if c['id']=='8880'][0]
for u in car['units']:
    if u['type'] in ('engine','steering_rack','steering_input','axle_with_differential','gearbox','lights','wing','suspension','driveline'):
        print(u['type'], u['section'], u['steps'], u['physical'], u['station_front0'], '|', (u['db_description'] or '')[:110])