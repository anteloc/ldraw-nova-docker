import json

# Define the house plan, fixing the section name to match pattern
plan = {
    "version": 1,
    "author": "Agent",
    "sections": [
        {
            "name": "main-scene.ldr",
            "description": "Main cottage assembly",
            "steps": [
                # Base
                {"id": "base-1", "ref": "3069b.dat", "colour": 7, "at": [0, 0, 0], "purpose": "Foundation"},
                # Simple wall corner for demonstration
                {"id": "wall-1", "ref": "3010.dat", "colour": 1, "at": [0, -28, 0], "purpose": "Wall corner"},
                {"id": "wall-2", "ref": "3010.dat", "colour": 1, "at": [80, -28, 0], "purpose": "Wall section"}
            ]
        }
    ]
}

with open('output/cottage.plan.json', 'w') as f:
    json.dump(plan, f, indent=2)
