import json

# Define the house plan, correcting the schema for placements
# The steps array should contain placements which are *objects*, not arrays,
# but the error says 'is not of type array'. Checking schema.
# Ah, looking at schema again - 'placement' definition.
# Wait, the error suggests steps is a list of arrays? No, 'items' is '$ref': '#/$defs/placement'.
# Let me look at example.plan.json structure in examples/modular-street/scene.plan.json
# Actually, the error message from the tool is confusing.
# Looking closer: "is not of type 'array'" means 'placement' IS expected to be an array?
# Let's re-read the instructions: "Each generated section has a unique flat .ldr name, useful description and steps of placement arrays."
# Ah, they are placement arrays! [colour, x, y, z, a, b, c, d, e, f, g, h, i, filename]
# Wait, no, the instructions say "Each placement has a unique local id, real ref, colour, and exactly one position mode".
# This means placements are objects.
# The schema error must be about something else.
# Re-reading: "placement" definition in schema might be a list.

# Let's try changing "at": [0,0,0] to be structured differently if needed,
# or perhaps the error is misleading and the schema expects [ref, colour, ...]?

# Actually, I will read the schema.
with open('ldraw_tools/data/plan.schema.json', 'r') as f:
    schema = json.load(f)
print(json.dumps(schema.get('$defs', {}).get('placement'), indent=2))
