p='output/prospect/census.py'
s=open(p).read()
# 1) bbox alias with .dat
s=s.replace("(normalized(ref).removesuffix('.dat'),)).fetchone()","(normalized(ref) if normalized(ref).endswith('.dat') else normalized(ref) + '.dat',)).fetchone()")
# 2) colour propagation
s=s.replace("def walk(sec, M, t, depth, inherited_uid):","def walk(sec, M, t, depth, inherited_uid, colour=16):")
s=s.replace("                Mc, tc = M @ mat(p), M @ vec(p) + t\n",
            "                Mc, tc = M @ mat(p), M @ vec(p) + t\n                code = p.colour.code if p.colour.code != 16 else colour\n")
s=s.replace("walk(child, Mc, tc, depth + 1, uid or inherited_uid)","walk(child, Mc, tc, depth + 1, uid or inherited_uid, code)")
s=s.replace("leaves.append(dict(ref=p.reference, desc=d, pos=tc, mat=Mc, unit=u))","leaves.append(dict(ref=p.reference, desc=d, pos=tc, mat=Mc, unit=u, colour=code))")
# 3) front detection
old=s[s.index("    steer_pos = ["):s.index("    def station(x):")]
new='''    mid = (lo[long_axis] + hi[long_axis]) / 2
    red = [l['pos'][long_axis] for l in leaves if l['colour'] == 36]
    clear = [l['pos'][long_axis] for l in leaves if l['colour'] in (47, 46, 43, 57, 182)]
    fr = [l['pos'][long_axis] for l in leaves if units[l['unit']]['section'] and re.search(r'front', units[l['unit']]['section'], re.I)]
    rr = [l['pos'][long_axis] for l in leaves if units[l['unit']]['section'] and re.search(r'rear|back', units[l['unit']]['section'], re.I)]
    racks = [l['pos'][long_axis] for l in leaves if re.search(r'Gear Rack', l['desc'] or '', re.I)]
    if red and clear and abs(np.mean(red) - np.mean(clear)) > 40:
        front_low, front_evidence = np.mean(clear) < np.mean(red), f'lights: {len(clear)} clear/yellow vs {len(red)} trans-red'
    elif fr and rr:
        front_low, front_evidence = np.mean(fr) < np.mean(rr), 'section names front vs rear/back'
    elif racks:
        front_low, front_evidence = np.median(racks) < mid, 'gear rack median'
    else:
        front_low, front_evidence = True, 'default'

'''
s=s.replace(old,new)
s=s.replace("long_axis='XZ'[long_axis // 2], units=out)","long_axis='XZ'[long_axis // 2], front_evidence=front_evidence, units=out)")
open(p,'w').write(s)
print('patched')