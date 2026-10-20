import json

plan = {
    "version": 1,
    "author": "LDraw Nova Agent",
    "assets": [
        "assets/piston-crank.mpd",
        "assets/steering-rack.mpd"
    ],
    "includes": [
        "assets/scene.plan.json"
    ],
    "sections": [
        {
            "name": "buggy-main.ldr",
            "description": "High-Performance Desert Buggy",
            "steps": []
        }
    ]
}

placements = []
id_counter = 1

def add(ref, colour, at, matrix=None, yaw=None, rot=None):
    global id_counter
    p = {
        "id": f"part-{id_counter}",
        "ref": ref,
        "colour": colour,
        "purpose": "buggy component",
        "at": at
    }
    if matrix:
        p["matrix"] = matrix
    elif yaw is not None:
        p["yaw"] = yaw
    elif rot is not None:
        p["matrix"] = rot
    placements.append(p)
    id_counter += 1

wheel_ref = "56145c03.dat"
axle_y = -30
track = 100    # narrowed a bit so chassis connects to wheels
wb_f = -120    
wb_r = 120     

add(wheel_ref, 0, [-track, axle_y, wb_f], yaw=180) # Front Left
add(wheel_ref, 0, [track, axle_y, wb_f], yaw=0)    # Front Right
add(wheel_ref, 0, [-track, axle_y, wb_r], yaw=180) # Rear Left
add(wheel_ref, 0, [track, axle_y, wb_r], yaw=0)    # Rear Right

# Chassis from technic-atlas (placed in the center, y=0 is bottom)
add("box-chassis.ldr", 16, [0, axle_y - 20, 0])

# Engine and steering
add("study-fa629497d114-00-42048---engine.ldr", 16, [0, axle_y - 60, wb_r], yaw=180)
add("study-9733eaa539d2-00-9393---steering.ldr", 16, [0, axle_y - 20, wb_f])

# A more spacious roll cage around the central cockpit
# Use 1x15 liftarms (32278) for the main lower sills
add("32278.dat", 4, [-50, axle_y - 100, 0]) 
add("32278.dat", 4, [50, axle_y - 100, 0])  

# Vertical B-pillars behind the seat (proper rigid rotation)
# Y-up pitch -90 (or similar) to make the beam vertical.
# [[1,0,0], [0,0,1], [0,-1,0]] has det +1.
rot_vert = [[1,0,0], [0,0,-1], [0,1,0]]
add("32525.dat", 71, [-50, axle_y - 150, 40], rot=rot_vert)
add("32525.dat", 71, [50, axle_y - 150, 40], rot=rot_vert)

# Front pillars (pitch approx 45 deg)
# cos(45)=0.70710678, sin(45)=0.70710678
c = 0.70710678
rot_45 = [[1,0,0], [0,c,-c], [0,c,c]]
add("32524.dat", 4, [-50, axle_y - 120, -100], rot=rot_45)
add("32524.dat", 4, [50, axle_y - 120, -100], rot=rot_45)

# Roof rails (1x11, 32525)
add("32525.dat", 4, [-50, axle_y - 210, -30])
add("32525.dat", 4, [50, axle_y - 210, -30])

# Roof crossbeams bridging 100 width (a 1x11 beam is 200 units long: 10 holes * 20 LDU = 200, so a 1x7 is 120 long)
add("32524.dat", 71, [0, axle_y - 210, -70], yaw=90) # 1x7
add("32524.dat", 71, [0, axle_y - 210, 10], yaw=90)  # 1x7

# Seat in the middle
add("32020.dat", 1, [0, axle_y - 40, -20], yaw=0)

plan["sections"][0]["steps"].append(placements)

with open("output/buggy.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

