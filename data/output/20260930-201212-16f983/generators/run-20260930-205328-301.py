p='output/prospect/census.py'
s=open(p).read()
old=s[s.index("        if runs and runs[-1]['section'] == u['section'] and (runs[-1]['_tag']"):s.index("            r = runs[-1]\n")]
new='''        same = bool(runs) and runs[-1]['section'] == u['section']
        cur = runs[-1]['_tag'] if runs else None
        # rule: same tag merges; untagged steps merge into untagged runs, or into a tagged run if tiny (<=6 parts)
        join = same and ((tag is not None and tag == cur) or (tag is None and (cur is None or len(u['leaves']) <= 6)))
        if join:
'''
s=s.replace(old,new)
open(p,'w').write(s)
import json
corpus={"note":"Technic car corpus for subassembly census. role=source: candidate to copy/adapt (medium); role=count: frequency statistics only.",
"cars":[
 {"id":"42039","file":"42039-1.mpd","name":"24 Hours Race Car","role":"source","size":"medium","parts":1300},
 {"id":"42096","file":"42096-1.mpd","name":"Porsche 911 RSR","role":"source","size":"medium","parts":1696},
 {"id":"8880","file":"8880-1.mpd","name":"Super Car","role":"source","size":"medium","parts":1410},
 {"id":"8865","file":"8865-1.mpd","name":"Test Car","role":"source","size":"medium","parts":910},
 {"id":"42093","file":"42093-1.mpd","name":"Chevrolet Corvette ZR1","role":"count","size":"small","parts":575},
 {"id":"42111","file":"42111-1.mpd","name":"Dom's Dodge Charger","role":"count","size":"medium","parts":None},
 {"id":"8448","file":"8448-1.mpd","name":"Super Street Sensation","role":"count","size":"medium","parts":None},
 {"id":"42056","file":"42056-1.mpd","name":"Porsche 911 GT3 RS","role":"count","size":"large","parts":3089},
 {"id":"42083","file":"42083-1.mpd","name":"Bugatti Chiron","role":"count","size":"large","parts":3692}]}
open('output/prospect/corpus.json','w').write(json.dumps(corpus,indent=1))
print('ok')