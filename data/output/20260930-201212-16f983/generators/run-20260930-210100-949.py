import json
R={c['id']:c for c in json.load(open('output/prospect/census.json'))}
want=[('42039','42039 - frontaxle.ldr',None),('42096','42096 - frontaxle.ldr',None),('8880','8880 - step15.ldr',None),
      ('42039','42039 - 24 Hours Race Car.ldr',[2,2]),('42039','42039 - motor.ldr',None),('8880','8880 - step13.ldr',None),
      ('42096','42096 - spoiler.ldr',None),('42093','42093 - spoiler.ldr',None),('42039','42039 - steeringrack.ldr',None),('42039','42039 - seat.ldr',None)]
for cid,sec,steps in want:
    car=R[cid]; la=2 if car['long_axis']=='Z' else 0; ca=2-la
    for u in car['units']:
        if u['section']==sec and (steps is None or u['steps']==steps):
            lo,hi=u['origin_bounds']
            print(f"{cid} {sec} {steps or ''}: parts {u['physical']}, across {hi[ca]-lo[ca]:.0f} LDU ({(hi[ca]-lo[ca])/20:.1f} st), along {hi[la]-lo[la]:.0f}, height {hi[1]-lo[1]:.0f}, pos {u['station_front0']}")
            break
# overall car sizes
for cid,car in R.items():
    pass