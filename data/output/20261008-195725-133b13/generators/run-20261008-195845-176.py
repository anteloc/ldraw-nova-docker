import json

# Ah! "steps": { "items": { "items": { "$ref": "#/$defs/placement" }, "type": "array" }, "type": "array" }
# So steps should be an array of arrays of placements (steps)!

plan = {
    "version": 1,
    "author": "Agent",
    "sections": [
        {
            "name": "main-scene.ldr",
            "description": "Main cottage assembly",
            "steps": [
                # Step 1: Foundation (array of placements)
                [
                    {"id": "base-1", "ref": "3069b.dat", "colour": 7, "at": [0, 0, 0], "purpose": "Foundation"}
                ],
                # Step 2: Walls (array of placements)
                [
                    {"id": "wall-1", "ref": "3010.dat", "colour": 1, "at": [0, -28, 0], "purpose": "Wall corner"},
                    {"id": "wall-2", "ref": "3010.dat", "colour": 1, "at": [80, -28, 0], "purpose": "Wall section"}
                ]
            ]
        }
    ]
}

with open('output/cottage.plan.json', 'w') as f:
    json.dump(plan, f, indent=2)
