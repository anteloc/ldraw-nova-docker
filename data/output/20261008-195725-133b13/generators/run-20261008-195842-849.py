import json

# Section schema
with open('ldraw_tools/data/plan.schema.json', 'r') as f:
    schema = json.load(f)
print(json.dumps(schema.get('$defs', {}).get('section'), indent=2))
