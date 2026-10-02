import sqlite3,json
c=sqlite3.connect('file:data/ldraw-info.db?mode=ro',uri=True)
print(c.execute("select * from PART_BBOXES where alias like '3705%' or alias like '32073%' limit 4").fetchall())
R=json.load(open('output/prospect/census.json'))
for car in R:
    eng=[u['station_front0'] for u in car['units'] if u['type']=='engine']
    diff=[u['station_front0'] for u in car['units'] if u['type']=='axle_with_differential']
    rack=[u['station_front0'] for u in car['units'] if u['type']=='steering_rack']
    print(car['id'], car['long_axis'], 'engine',eng[:4],'diff',diff,'rack',rack)