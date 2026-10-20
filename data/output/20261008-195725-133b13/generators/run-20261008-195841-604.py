import json

# The schema definition for 'placement' shows 'at' should be a vector.
# Let me look at the vector definition.
# Actually, the error message: "is not of type 'array'" for the whole placement object?
# No, "is not of type 'array'" for "steps: [ ... ]".
# The error says "On instance['sections'][0]['steps'][0]".
# Wait, if steps[0] is an object, why does it complain it's not an array?
# Maybe 'steps' in the section should be an array of arrays, and the schema description in the instructions was slightly off?
# Let's check 'sections' definition in the schema.
with open('ldraw_tools/data/plan.schema.json', 'r') as f:
    schema = json.load(f)
print(json.dumps(schema.get('properties', {}).get('sections'), indent=2))
