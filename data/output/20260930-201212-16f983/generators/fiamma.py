"""Fiamma V8 generator: builds output/fiamma.plan.json and (optionally) the MPD via the toolkit.

Sources (attributed in section descriptions and output/sources.json):
  - 42039-1.mpd "24 Hours Race Car" (LEGO Group set, annotated OMR copy in data/models-annotated):
    rolling-chassis units adapted in the car frame (see output/phase3/*). Rotations snapped to proper rotations.
  - 42112 gearshift: pattern for the 2-speed driving-ring gearbox (re-built here with our own shafts).
New/original: gearbox integration, rear-bay re-arrangement, steering-wheel transfer, cockpit, body, doors, wing.

Car frame: X across (+X driver side), -Z forward, Y=0 road, negative Y up, Z=0 front-axle centre.
Run: .venv/bin/python output/generators/fiamma.py [--build]
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import OrderedDict

import numpy as np

sys.path.insert(0, 'output/generators')
import fz  # noqa: E402

REAR_SHIFT = 80.0                       # rear-axle unit moved back along the side rails (wheelbase 740 -> 820)
I3 = np.eye(3)
AX_Z = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float)   # local +X (axles/pins) -> world +Z

STRUCT_WORDS = ('Beam', 'Liftarm', 'Cross Block', 'Connector', 'Frame', 'Steering Arm', 'Suspension Arm',
                'Pin Joiner', 'Brick', 'Toggle')
RECOLOUR = {71: 72, 14: 0, 10: 0, 15: 72, 28: 72, 27: 0, 191: 0}   # structure palette: dark bluish grey + black


class Section:
    def __init__(self, name, description, author='LDraw Astra agent (Fiamma V8 generator)'):
        self.name, self.description, self.author = name, description, author
        self.steps = [[]]
        self.ids = set()

    def step(self):
        if self.steps[-1]:
            self.steps.append([])

    def add(self, ref, colour, t, M=I3, purpose=None, pid=None):
        ref = ref if ref.lower().endswith(('.dat', '.ldr')) else ref + '.dat'
        base = pid or ref.lower().removesuffix('.dat').replace('.', '-')
        k, pid = 0, base
        while pid in self.ids:
            k += 1
            pid = f'{base}-{k}'
        self.ids.add(pid)
        M = np.asarray(M, float)
        assert abs(np.linalg.det(M) - 1) < 1e-6 and np.allclose(M.T @ M, I3, atol=1e-6), (ref, M)
        e = OrderedDict(id=pid, ref=ref, colour=int(colour),
                        at=[round(float(v), 4) for v in t],
                        matrix=[[round(float(v), 9) for v in row] for row in M])
        if purpose:
            e['purpose'] = purpose
        self.steps[-1].append(e)
        return e

    def count(self):
        return sum(len(s) for s in self.steps)

    def plan(self):
        return OrderedDict(name=self.name, description=self.description, author=self.author,
                           steps=[s for s in self.steps if s])


# ----------------------------------------------------------------------------------------------
DONOR = fz.load_donor()


def near(r, pos, tol=1.5):
    return np.allclose(r['t'], pos, atol=tol)


def removed(r):
    """Donor parts deleted for the new rear bay / gearbox / body (reasons in NOTES)."""
    ref, st, unit = r['ref'], r['step'], r['unit']
    if 'RibHose' in unit:
        return 'flexible hose pseudo-part'
    if st == 1 and ref in ('60484.dat', '6587.dat'):
        return 'engine-rear link / old pinion axle replaced by gearbox'
    if st == 1 and ref == '6558.dat' and abs(r['t'][1] + 100) < 1:
        return 'engine-rear link'
    if 'motor' in unit and ref in ('44294.dat', '3713.dat', '62462.dat'):
        return 'crank extension replaced by gearbox shaft B'
    if 'motor' in unit and ref == '6558.dat' and abs(r['t'][1] + 100) < 1:
        return 'engine-rear link'
    if st == 16 and unit == 'main' and ref == '32270.dat':
        return 'direct 12T drive replaced by gearbox'
    if st == 19 and ref == '6558.dat' and r['t'][2] > 630:
        return 'pinned into rear unit before it moved'
    if st == 22 and unit == 'main' and ref != '41239.dat':
        return 'hose anchors'
    if st == 22 and ref == '41239.dat':
        return 'door-lift support (own doors)'
    if st in (25, 26):
        return 'donor door-lift drive shafts (own doors)'
    if ref == '4254.dat':
        return 'shock rod merged into 73129'
    return None


def colour_of(r, module):
    c = r['colour']
    if module == 'engine':
        return c
    d = r['desc']
    if any(w in d for w in STRUCT_WORDS) and 'Engine' not in d:
        return RECOLOUR.get(c, c)
    return c


def add_donor(sec, rows, module, shift=np.zeros(3)):
    last = None
    for r in rows:
        if last is not None and r['step'] != last:
            sec.step()
        last = r['step']
        ref, col, M, t = r['ref'], colour_of(r, module), r['M'], r['t'] + shift
        purpose = f"42039 step {r['step']}" + (f" ({r['unit'][8:]})" if r['unit'] != 'main' else '')
        if ref == '4255.dat':      # shock cylinder at the donor shock-submodel origin -> complete library shock
            sec.add('73129.dat', 25, t, M, purpose + ': complete 6.5L shock replaces raw spring mesh')
            continue
        sec.add(ref, col, t, M, purpose)


def pick(pred):
    return [r for r in DONOR if pred(r) and not removed(r)]


# ---------------------------------------------------------------------------------------------- modules
def m2_rear_axle():
    s = Section('fz-m2-rear-axle.ldr', 'M2 rear axle: 62821 differential, CV half-shafts, independent '
                'wishbones and two 73129 shocks. Adapted from 42039 steps 1-10, 15, 17 (moved back 80 LDU; '
                'old pinion axle and engine link removed).')
    rows = pick(lambda r: r['step'] <= 10 or r['step'] in (15, 17))
    add_donor(s, rows, 'rear', np.array([0, 0, REAR_SHIFT]))
    return s


def m1_frame():
    s = Section('fz-m1-frame.ldr', 'M1 frame: side rails, firewall hoop, engine cradle, cockpit floor and front '
                'floor. Adapted from 42039 steps 11-14, 18-24, 27-28, 30, 33 (door-lift and hose parts removed).')
    rows = pick(lambda r: r['step'] in (11, 12, 13, 14, 18, 19, 20, 21, 22, 23, 24, 27, 28, 30, 33)
                and 'motor' not in r['unit'])
    add_donor(s, rows, 'frame')
    return s


def m4_engine():
    s = Section('fz-m4-engine.ldr', 'M4 V8 piston engine (8 pistons, 4 crank centres) from 42039 motor.ldr; '
                'rear crank extension replaced by gearbox shaft B.')
    add_donor(s, pick(lambda r: 'motor' in r['unit']), 'engine')
    return s


def m5_front_axle():
    s = Section('fz-m5-front-axle.ldr', 'M5 front axle: double wishbones, portal steering hubs, rack carriage and '
                'two 73129 shocks. From 42039 frontaxle.ldr, steeringrack.ldr and frontaxletop.ldr (steps 29, 32).')
    add_donor(s, pick(lambda r: r['step'] in (29, 32)), 'front')
    return s


def m6_steering():
    s = Section('fz-m6-steering.ldr', 'M6 steering input: tunnel shaft from the rack pinion to the rear-deck knob '
                '(42039 step 31).')
    add_donor(s, pick(lambda r: r['step'] == 31), 'steer')
    return s


def m3_gearbox():
    s = Section('fz-m3-gearbox.ldr', 'M3 two-speed gearbox (pattern: 42112 gearshift). Shaft A (Y=-100) carries '
                'fixed 16T and 12T gears and the diff pinion; shaft B (Y=-60, crank) carries free 16T/20T clutch '
                'gears either side of a driving ring. Ratios 16:16 and 12:20.')
    s.add('3737', 72, (0, -100, 690), AX_Z, 'shaft A: 10L from engine rear brick through rear frame block to pinion')
    s.add('94925', 72, (0, -100, 620), I3, 'fixed 16T, 1st-gear pair')
    s.add('32270', 0, (0, -100, 700), I3, 'fixed 12T double bevel, 2nd-gear pair')
    s.step()
    s.add('3705', 72, (0, -60, 620), AX_Z, 'shaft B front: 4L from crank end into joiner')
    s.add('18946', 72, (0, -60, 620), I3, 'free 16T clutch gear (1st)')
    s.add('18948', 72, (0, -60, 660), I3, 'joiner with driving-ring ridges couples shaft B halves')
    s.add('18947', 72, (0, -60, 660), I3, 'driving ring, neutral pose')
    s.add('4519', 72, (0, -60, 690), AX_Z, 'shaft B rear stub: 3L')
    s.add('35185', 0, (0, -60, 700), I3, 'free 20T double-bevel clutch gear (2nd)')
    return s


def m12_wheels():
    s = Section('fz-m12-wheels.ldr', 'M12 wheels: 15038 rims (flat silver) with 44771 ZR tyres, positions from '
                '42039 (rear moved back 80).')
    for r in DONOR:
        if r['ref'] in ('15038.dat', '44771.dat'):
            shift = np.array([0, 0, REAR_SHIFT]) if r['t'][2] > 300 else np.zeros(3)
            col = 179 if r['ref'] == '15038.dat' else 256
            s.add(r['ref'], col, r['t'] + shift, r['M'], 'rim' if col == 179 else 'tyre')
    return s


MODULES = [m1_frame, m2_rear_axle, m3_gearbox, m4_engine, m5_front_axle, m6_steering, m12_wheels]


def main_section(mods):
    s = Section('fiamma-v8.ldr', 'Fiamma V8 - orange/black mid-engine Technic hypercar (work in progress)')
    for m in mods:
        s.add(m.name, 72, (0, 0, 0), I3, m.description.split(':')[0])
        s.step()
    return s


def build_plan():
    mods = [f() for f in MODULES]
    main = main_section(mods)
    plan = OrderedDict(version=1, author='LDraw Astra agent for carlos.antelo (Fiamma V8); donor geometry from '
                       'LEGO set 42039 via data/models-annotated',
                       sections=[main.plan()] + [m.plan() for m in mods])
    counts = {m.name: m.count() for m in mods}
    return plan, counts


if __name__ == '__main__':
    plan, counts = build_plan()
    json.dump(plan, open('output/fiamma.plan.json', 'w'), indent=1)
    print('placements', counts, 'total', sum(counts.values()))
    if '--build' in sys.argv:
        r = subprocess.run(['./ldraw-agent', 'build', 'output/fiamma.plan.json', '--output', 'output/fiamma-v8.mpd',
                            '--force', '--contacts', 'none', '--detail', 'summary',
                            '--report', 'output/fiamma-v8.build.json'], capture_output=True, text=True)
        rep = json.load(open('output/fiamma-v8.build.json')) if r.returncode in (0, 1) else {}
        diags = rep.get('diagnostics', []) + (rep.get('geometry') or {}).get('diagnostics', [])
        from collections import Counter
        print('build exit', r.returncode, Counter((d.get('code'), d.get('severity')) for d in diags).most_common(12))
        if r.returncode == 2:
            print(r.stderr[-1500:])
