"""Read-only census of Technic car references: find recurring subassembly types.

Uses pyldraw3 (via ldraw_tools.document.parse_source) for all record parsing.
Outputs: output/prospect/census.json and output/prospect/census.md
Run:  .venv/bin/python output/prospect/census.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, '.')
from ldraw_tools.common import get_parts, normalized  # noqa: E402
from ldraw_tools.document import parse_source, section_table, is_part  # noqa: E402

OUT = Path('output/prospect')
CORPUS = json.loads((OUT / 'corpus.json').read_text())
DB = sqlite3.connect('file:data/ldraw-info.db?mode=ro', uri=True)
PARTS = get_parts()

# ---- signature rules: library description regex -> signature tag -------------------------
SIG = [
    ('differential', r'\bDifferential\b'),
    ('engine', r'Engine Piston|Engine Cylinder|Engine Crankshaft|Technic Piston\s+2|Crankshaft'),
    ('gearbox', r'Driving Ring|Changeover|with Clutch|Gearbox|Shifter|Gear Shift'),
    ('steering_rack', r'Gear Rack|Toothed Bar|Steering Rack|Rack Holder'),
    ('knuckle_hub', r'Steering Arm|Steering Knuckle|Steering Portal|Wheel Hub|Steering Link|Knuckle|Steering Wheel Bearing|Portal Axle|Large Wheel Hub|Hub Wheel'),
    ('steering_input', r'Steering Wheel(?! Hub| Bearing)'),
    ('suspension', r'Shock Absorber|Suspension|Wishbone|\bSpring\b|Damper'),
    ('cv_ujoint', r'Universal Joint|\bCV\b|Constant Velocity|Ball Cup|Axle Ball Joint'),
    ('seat', r'\bSeat\b'),
    ('door', r'\bDoor\b'),
    ('hinge', r'Hinge'),
    ('panel', r'\bPanel\b'),
    ('windscreen', r'Windscreen|Windshield'),
    ('tyre_wheel', r'\bTyre\b|\bTire\b|\bRim\b|^Wheel|\bWheel (?!Hub)'),
    ('gear', r'\bGear\b'),
    ('axle', r'Technic Axle\s+\d'),
    ('beam', r'Technic Beam|Liftarm|Technic Brick'),
]
SIG_RE = [(t, re.compile(r, re.I)) for t, r in SIG]
STRONG = ['differential', 'engine', 'gearbox', 'steering_rack', 'steering_input', 'knuckle_hub',
          'suspension', 'cv_ujoint', 'seat', 'door', 'windscreen', 'tyre_wheel']
# name/description keyword -> unit type (fallback after signatures)
NAME_RULES = [
    ('engine', r'engine|motor|\bv8\b|\bv6\b|\bw16\b|cylinder|piston'),
    ('gearbox', r'gearbox|gear ?box|transmission|shift'),
    ('steering', r'steer'),
    ('front_axle_susp', r'front ?axle|frontaxle|front suspension'),
    ('rear_axle_susp', r'rear ?axle|rearaxle|rear suspension'),
    ('suspension', r'shock|suspension|spring'),
    ('door', r'door'),
    ('seat_cockpit', r'seat|dashboard|cockpit|interior'),
    ('wing', r'wing|spoiler'),
    ('lights', r'light|lamp'),
    ('exhaust', r'exhaust'),
    ('wheel', r'wheel|tyre|tire'),
    ('frame', r'chassis|frame|floor|tub'),
    ('body', r'panel|body|side|hood|bonnet|roof|top|front|rear|back|mudguard|fender|bumper|grille|cover|nose|tail'),
]
NAME_RE = [(t, re.compile(r, re.I)) for t, r in NAME_RULES]


def desc_of(ref, table):
    key = normalized(ref)
    if key in table:
        return table[key].description or ref
    return PARTS.by_code.get(key.removesuffix('.dat'), '')


def sig_tags(desc):
    return [t for t, rx in SIG_RE if rx.search(desc or '')]


def mat(p):
    m = p.matrix
    rows = getattr(m, 'rows', m)
    return np.array([[float(v) for v in r] for r in rows])


def vec(p):
    v = p.position
    return np.array([float(v.x), float(v.y), float(v.z)])


def bbox_axis(ref):
    row = DB.execute('select min_x,min_y,min_z,max_x,max_y,max_z from PART_BBOXES where alias=?',
                     (normalized(ref) if normalized(ref).endswith('.dat') else normalized(ref) + '.dat',)).fetchone()
    if not row:
        return None
    ext = np.array(row[3:]) - np.array(row[:3])
    return int(np.argmax(ext)), float(ext.max())


def classify(unit):
    sigs = unit['signatures']
    s = lambda k: sigs.get(k, 0)
    tags = []
    if s('differential'):
        tags.append('axle_with_differential')
    if s('engine') >= 2:
        tags.append('engine')
    if s('gearbox'):
        tags.append('gearbox')
    if s('steering_rack'):
        tags.append('steering_rack')
    if s('knuckle_hub') and (s('suspension') or s('cv_ujoint')):
        tags.append('axle_suspension')
    elif s('knuckle_hub'):
        tags.append('knuckle_hub')
    elif s('suspension'):
        tags.append('suspension')
    if s('steering_input'):
        tags.append('steering_input')
    if s('cv_ujoint') and not s('knuckle_hub'):
        tags.append('driveline')
    if s('seat'):
        tags.append('seat_cockpit')
    if s('door'):
        tags.append('door')
    if s('windscreen'):
        tags.append('windscreen')
    if s('tyre_wheel') >= 2:
        tags.append('wheel')
    unit['signature_tags'] = tags
    text = f"{unit['section']} {unit.get('db_description') or ''}"
    name_tags = [t for t, rx in NAME_RE if rx.search(unit['section'])]
    desc_tags = [t for t, rx in NAME_RE if rx.search(unit.get('db_description') or '')]
    unit['name_tags'], unit['desc_tags'] = name_tags, desc_tags
    if tags:
        unit['type'], unit['type_source'] = tags[0], 'signature'
    elif name_tags and name_tags[0] != 'body':
        unit['type'], unit['type_source'] = name_tags[0], 'name'
    elif desc_tags:
        unit['type'], unit['type_source'] = desc_tags[0], 'db_description'
    elif s('panel') >= 2:
        unit['type'], unit['type_source'] = 'body', 'panels'
    elif name_tags:
        unit['type'], unit['type_source'] = name_tags[0], 'name'
    elif unit['technic_share'] >= 0.7 and s('beam') >= 3:
        unit['type'], unit['type_source'] = 'frame', 'technic_share'
    else:
        unit['type'], unit['type_source'] = 'unclassified', None
    return unit


def survey(entry):
    path = Path('data/models-annotated') / entry['file']
    model = parse_source(path)
    table = section_table(model)
    main = model
    dbdesc = dict(DB.execute('select submodel, description from SUBMODELS_DESCRIPTIONS where model=?',
                             (entry['file'],)).fetchall())
    dbdesc = {normalized(k): v for k, v in dbdesc.items()}

    # leaf occurrences with world transform + owning unit id
    leaves = []  # dict(ref, desc, pos, mat, unit)
    units = {}

    def direct_count(sec):
        return sum(1 for _ in sec.pieces)

    def new_unit(uid, section, step_range=None):
        units[uid] = dict(id=uid, model=entry['id'], section=section.name, steps=step_range,
                          db_description=dbdesc.get(normalized(section.name)), leaves=[])
        return uid

    def walk(sec, M, t, depth, inherited_uid, colour=16):
        key = normalized(sec.name)
        split = direct_count(sec) > 100
        own_uid = None
        if not split and inherited_uid is None or (not split and depth > 0 and direct_count(sec) >= 5):
            own_uid = new_unit(f"{entry['id']}::{sec.name}#{len(units)}", sec)
        for si, step in enumerate(sec.steps, 1):
            uid = own_uid
            if split:
                uid = new_unit(f"{entry['id']}::{sec.name}::step{si}#{len(units)}", sec, [si, si])
            for p in step:
                if not hasattr(p, 'reference'):
                    continue
                Mc, tc = M @ mat(p), M @ vec(p) + t
                code = p.colour.code if p.colour.code != 16 else colour
                child = table.get(normalized(p.reference))
                if child is not None and not is_part(child):
                    walk(child, Mc, tc, depth + 1, uid or inherited_uid, code)
                else:
                    u = uid or inherited_uid
                    d = desc_of(p.reference, table)
                    leaves.append(dict(ref=p.reference, desc=d, pos=tc, mat=Mc, unit=u, colour=code))
                    units[u]['leaves'].append(len(leaves) - 1)

    walk(main, np.eye(3), np.zeros(3), 0, None)

    # merge consecutive step-units of split sections by tag
    def unit_sig(u):
        c = Counter()
        for i in u['leaves']:
            for tag in sig_tags(leaves[i]['desc']):
                c[tag] += 1
        return c

    merged = {}
    order = list(units)
    runs = []
    for uid in order:
        u = units[uid]
        if u['steps'] is None:
            merged[uid] = u
            continue
        sig = unit_sig(u)
        tag = next((t for t in STRONG if sig.get(t)), None)
        if not u['leaves']:
            continue
        same = bool(runs) and runs[-1]['section'] == u['section']
        cur = runs[-1]['_tag'] if runs else None
        # rule: same tag merges; untagged steps merge into untagged runs, or into a tagged run if tiny (<=6 parts)
        join = same and ((tag is not None and tag == cur) or (tag is None and (cur is None or len(u['leaves']) <= 6)))
        if join:
            r = runs[-1]
            r['leaves'] += u['leaves']
            r['steps'][1] = u['steps'][1]
            for i in u['leaves']:
                leaves[i]['unit'] = r['id']
        else:
            u = dict(u, _tag=tag)
            runs.append(u)
            for i in u['leaves']:
                leaves[i]['unit'] = u['id']
    for r in runs:
        r.pop('_tag', None)
        merged[r['id']] = r
    units = {k: v for k, v in merged.items() if v['leaves']}

    # global long axis / front direction
    P = np.array([l['pos'] for l in leaves])
    lo, hi = P.min(0), P.max(0)
    long_axis = 0 if (hi[0] - lo[0]) >= (hi[2] - lo[2]) else 2
    mid = (lo[long_axis] + hi[long_axis]) / 2
    red = [l['pos'][long_axis] for l in leaves if l['colour'] == 36]
    clear = [l['pos'][long_axis] for l in leaves if l['colour'] in (47, 46, 43, 57, 182)]
    fr = [l['pos'][long_axis] for l in leaves if units[l['unit']]['section'] and re.search(r'front', units[l['unit']]['section'], re.I)]
    rr = [l['pos'][long_axis] for l in leaves if units[l['unit']]['section'] and re.search(r'rear|back', units[l['unit']]['section'], re.I)]
    racks = [l['pos'][long_axis] for l in leaves if re.search(r'Gear Rack', l['desc'] or '', re.I)]
    txt = lambda l: f"{units[l['unit']]['section']} {units[l['unit']].get('db_description') or ''}"
    hl = [l['pos'][long_axis] for l in leaves if re.search(r'headl', txt(l), re.I)]
    wg = [l['pos'][long_axis] for l in leaves if re.search(r'spoiler|rear wing|tail ?light', txt(l), re.I)]
    if red and clear and abs(np.mean(red) - np.mean(clear)) > 40:
        front_low, front_evidence = np.mean(clear) < np.mean(red), f'lights: {len(clear)} clear/yellow vs {len(red)} trans-red'
    elif hl and wg:
        front_low, front_evidence = np.mean(hl) < np.mean(wg), f'headlight units vs wing/tail units'
    elif fr and rr:
        front_low, front_evidence = np.mean(fr) < np.mean(rr), 'section names front vs rear/back'
    elif racks:
        front_low, front_evidence = np.median(racks) < mid, 'gear rack median'
    else:
        front_low, front_evidence = True, 'default'

    def station(x):
        f = (x - lo[long_axis]) / max(hi[long_axis] - lo[long_axis], 1)
        return f if front_low else 1 - f

    # per-unit stats
    out = []
    for uid, u in units.items():
        idx = u['leaves']
        refs = Counter(leaves[i]['ref'].lower() for i in idx)
        sig = Counter()
        sig_parts = defaultdict(Counter)
        technic = 0
        for i in idx:
            d = leaves[i]['desc'] or ''
            technic += d.startswith('Technic')
            for tag in sig_tags(d):
                sig[tag] += 1
                sig_parts[tag][f"{leaves[i]['ref'].lower()} | {d}"] += 1
        pts = np.array([leaves[i]['pos'] for i in idx])
        rec = dict(id=uid, model=u['model'], section=u['section'], steps=u['steps'],
                   db_description=u['db_description'], physical=len(idx),
                   technic_share=round(technic / len(idx), 2),
                   signatures=dict(sig),
                   signature_parts={k: dict(v.most_common(6)) for k, v in sig_parts.items() if k in STRONG},
                   origin_bounds=[pts.min(0).round(1).tolist(), pts.max(0).round(1).tolist()],
                   station_front0=round(float(station(pts[:, long_axis].mean())), 2),
                   top_parts=[f"{r} x{n}" for r, n in refs.most_common(8)])
        out.append(classify(rec))

    # neighbours (origin proximity) and axle crossings
    unit_pts = {u['id']: np.array([leaves[i]['pos'] for i in units[u['id']]['leaves']]) for u in out}
    for u in out:
        near = Counter()
        crossings = Counter()
        mine = unit_pts[u['id']]
        for other in out:
            if other['id'] == u['id']:
                continue
            op = unit_pts[other['id']]
            dmin = np.min(np.linalg.norm(mine[:, None, :] - op[None, :, :], axis=2)) if len(mine) * len(op) < 4e6 else 999
            if dmin <= 25:
                near[other['type']] += 1
        for i in units[u['id']]['leaves']:
            l = leaves[i]
            if not re.search(r'Technic Axle\s+\d', l['desc'] or ''):
                continue
            ax = bbox_axis(l['ref'])
            if not ax:
                continue
            direction = l['mat'][:, ax[0]]
            half = ax[1] / 2
            for other in out:
                if other['id'] == u['id']:
                    continue
                rel = unit_pts[other['id']] - l['pos']
                along = rel @ direction
                perp = np.linalg.norm(rel - np.outer(along, direction), axis=1)
                if np.any((np.abs(along) <= half) & (perp <= 12)):
                    crossings[other['type']] += 1
        u['neighbour_types'] = dict(near)
        u['axle_crossings_into'] = dict(crossings)
    return dict(id=entry['id'], file=entry['file'], role=entry['role'], physical=len(leaves),
                long_axis='XZ'[long_axis // 2], front_evidence=front_evidence, units=out)


def main():
    results = []
    for entry in CORPUS['cars']:
        try:
            r = survey(entry)
        except Exception as exc:  # record, do not hide
            r = dict(id=entry['id'], file=entry['file'], role=entry['role'], error=repr(exc), units=[])
        results.append(r)
        n = Counter(u['type'] for u in r['units'])
        print(entry['id'], r.get('physical'), 'units', len(r['units']), dict(n.most_common(12)), r.get('error', ''))
    (OUT / 'census.json').write_text(json.dumps(results, indent=1, default=float))


if __name__ == '__main__':
    main()
