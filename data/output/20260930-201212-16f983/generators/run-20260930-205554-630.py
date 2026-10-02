p='output/prospect/census.py'
s=open(p).read()
old="    racks = [l['pos'][long_axis] for l in leaves if re.search(r'Gear Rack', l['desc'] or '', re.I)]\n"
new=old+'''    txt = lambda l: f"{units[l['unit']]['section']} {units[l['unit']].get('db_description') or ''}"
    hl = [l['pos'][long_axis] for l in leaves if re.search(r'headl', txt(l), re.I)]
    wg = [l['pos'][long_axis] for l in leaves if re.search(r'spoiler|rear wing|tail ?light', txt(l), re.I)]
'''
s=s.replace(old,new)
s=s.replace("    elif fr and rr:\n","    elif hl and wg:\n        front_low, front_evidence = np.mean(hl) < np.mean(wg), f'headlight units vs wing/tail units'\n    elif fr and rr:\n")
open(p,'w').write(s)