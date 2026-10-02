p='output/prospect/census.py'
s=open(p).read()
s=s.replace("('engine', r'Engine Piston|Engine Cylinder|Engine Crankshaft|\\bPiston\\b|Crankshaft'),",
            "('engine', r'Engine Piston|Engine Cylinder|Engine Crankshaft|Technic Piston\\s+2|Crankshaft'),")
s=s.replace("('knuckle_hub', r'Steering Arm|Steering Knuckle|Steering Portal|Wheel Hub|Hub\\b|Steering Link|Knuckle'),",
            "('knuckle_hub', r'Steering Arm|Steering Knuckle|Steering Portal|Wheel Hub|Steering Link|Knuckle|Steering Wheel Bearing|Portal Axle|Hub with'),")
s=s.replace("('steering_input', r'Steering Wheel'),","('steering_input', r'Steering Wheel(?! Hub| Bearing)'),")
assert "Technic Piston\\s+2" in s and "Steering Wheel(?! Hub" in s and "Steering Wheel Bearing|Portal" in s
open(p,'w').write(s)
import re
# make sure 'Hub with' doesn't catch connector hub:
print(bool(re.search(r'Hub with','Technic Axle and Pin Connector Hub with 2 Axles at 90 Degrees')))