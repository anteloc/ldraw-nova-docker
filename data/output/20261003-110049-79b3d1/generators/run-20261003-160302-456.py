
import pathlib
p = pathlib.Path("output/garden-cottage/generate.py")
s = p.read_text()

# Remove the broken shuttered window module.
start = s.index('def window4_shuttered(')
end = s.index('def entry_door(')
s = s[:start] + s[end:]

# All hall windows are now plain bays.
s = s.replace("""            else:
                if s == "front" and centre == -4 and r0 == 1:
                    m.add(window4_shuttered(), WHITE, x, 8 + 24*r0, z, yaw=yaw)
                else:
                    m.add(window4(WHITE, GLASS), WHITE, x, 8 + 24*r0, z, yaw=yaw)""",
"""            else:
                m.add(window4(WHITE, GLASS), WHITE, x, 8 + 24*r0, z, yaw=yaw)""")

# Drop window4-shuttered from the section order list.
s = s.replace('"window4-shuttered", ', '')
p.write_text(s)
print("shutters removed")
