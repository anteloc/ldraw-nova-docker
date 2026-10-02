"""Summarize census.json into census.md (frequency table + candidate units per family)."""
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path('output/prospect')
R = json.loads((OUT / 'census.json').read_text())

FAMILY = {
    'axle_with_differential': 'rear axle + differential', 'rear_axle_susp': 'rear axle + differential',
    'axle_suspension': 'axle suspension / knuckles', 'front_axle_susp': 'axle suspension / knuckles',
    'knuckle_hub': 'axle suspension / knuckles', 'suspension': 'axle suspension / knuckles',
    'steering_rack': 'steering (rack/column/input)', 'steering': 'steering (rack/column/input)',
    'steering_input': 'steering (rack/column/input)',
    'engine': 'piston engine', 'gearbox': 'gearbox', 'driveline': 'driveline (UJ/CV shafts)',
    'seat_cockpit': 'cockpit / seats', 'windscreen': 'cockpit / seats', 'door': 'doors', 'wing': 'rear wing / spoiler',
    'lights': 'lights', 'exhaust': 'exhaust', 'frame': 'frame / chassis', 'body': 'body panels',
    'wheel': 'wheels', 'unclassified': 'unclassified',
}
# car-level presence evidence from signature parts (independent of unit typing)
CAR_SIG = {
    'rear axle + differential': ['differential'], 'axle suspension / knuckles': ['suspension', 'knuckle_hub'],
    'steering (rack/column/input)': ['steering_rack', 'steering_input'], 'piston engine': ['engine'],
    'gearbox': ['gearbox'], 'driveline (UJ/CV shafts)': ['cv_ujoint'],
}


def where(x):
    return 'front' if x < 0.35 else 'rear' if x > 0.62 else 'middle'


fam_units = defaultdict(list)
car_has = defaultdict(set)
for car in R:
    carsig = Counter()
    for u in car['units']:
        fam = FAMILY.get(u['type'], u['type'])
        fam_units[fam].append((car, u))
        car_has[fam].add(car['id'])
        for k, v in u['signatures'].items():
            carsig[k] += v
    for fam, keys in CAR_SIG.items():
        if any(carsig.get(k) for k in keys):
            car_has[fam].add(car['id'])

cars = [c['id'] for c in R]
lines = ['# Technic car subassembly census', '',
         f"Corpus: {len(R)} cars ({', '.join(cars)}); {sum(c.get('physical', 0) for c in R)} physical placements. "
         'Source: `census.py` (read-only, pyldraw3 parse). Units = named sections, or instruction-step runs of flat '
         'sections with >100 direct placements, merged by identifying-part tag. Position is the unit centroid along the '
         'car length (0 = front, set by steering parts). Neighbours = other units whose part origins are within 25 LDU; '
         'axle crossings = other units whose part origins lie on this unit\'s axle segments (≤12 LDU off axis). '
         'All are approximations from origins, not solid geometry.', '',
         '## Frequency by family', '',
         '| Family | Cars (of 9) | Units | Median parts/unit | Typical position | Common identifying parts | Usual neighbours / axle crossings |',
         '|---|---:|---:|---:|---|---|---|']
order = sorted(fam_units, key=lambda f: (-len(car_has[f]), f))
for fam in order:
    us = [u for _, u in fam_units[fam]]
    sizes = [u['physical'] for u in us]
    pos = Counter(where(u['station_front0']) for u in us).most_common(2)
    sig = Counter()
    nb, cx = Counter(), Counter()
    for u in us:
        for tag, parts in u['signature_parts'].items():
            for k, n in parts.items():
                sig[k.split(' | ')[0]] += n
        for k, v in u['neighbour_types'].items():
            nb[FAMILY.get(k, k)] += 1
        for k, v in u['axle_crossings_into'].items():
            cx[FAMILY.get(k, k)] += v
    nb.pop(fam, None)
    cx.pop(fam, None)
    lines.append(f"| {fam} | {len(car_has[fam])} | {len(us)} | {int(st.median(sizes))} | "
                 f"{', '.join(f'{p} {n}' for p, n in pos)} | {', '.join(k for k, _ in sig.most_common(5)) or '—'} | "
                 f"nb: {', '.join(k for k, _ in nb.most_common(3))}; ax: {', '.join(k for k, _ in cx.most_common(3)) or '—'} |")

lines += ['', '## Candidate units in medium source cars (role=source)', '']
KEY = ['rear axle + differential', 'axle suspension / knuckles', 'steering (rack/column/input)', 'piston engine',
       'gearbox', 'driveline (UJ/CV shafts)', 'cockpit / seats', 'doors', 'rear wing / spoiler', 'frame / chassis']
cand = {}
for fam in KEY:
    rows = [(c, u) for c, u in fam_units[fam] if c['role'] == 'source' and u['physical'] >= 4]
    rows.sort(key=lambda cu: -cu[1]['physical'])
    lines += [f'### {fam}', '', '| Unit | Parts | Steps | Pos | Technic % | Identifying parts | Axles cross into |', '|---|---:|---|---|---:|---|---|']
    cand[fam] = []
    for c, u in rows[:8]:
        sp = '; '.join(f"{k.split(' | ')[0]}×{n}" for t, parts in u['signature_parts'].items() for k, n in list(parts.items())[:2])
        lines.append(f"| {c['id']} `{u['section']}` | {u['physical']} | {u['steps'] or 'all'} | {where(u['station_front0'])} "
                     f"{u['station_front0']} | {int(100 * u['technic_share'])} | {sp or '—'} | "
                     f"{', '.join(f'{FAMILY.get(k, k)}' for k in u['axle_crossings_into']) or '—'} |")
        cand[fam].append(dict(car=c['id'], file=c['file'], section=u['section'], steps=u['steps'], physical=u['physical'],
                              station=u['station_front0'], db_description=u['db_description']))
    lines.append('')
(OUT / 'census.md').write_text('\n'.join(lines) + '\n')
(OUT / 'candidates.json').write_text(json.dumps(cand, indent=1))
print('\n'.join(lines[:30]))
