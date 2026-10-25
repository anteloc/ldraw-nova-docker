
import json
r=json.load(open('output/kestrel/review/review.json'))
print(r.keys())
v=json.load(open('output/kestrel/review/validation.json'))
from collections import Counter
print(Counter((d['code'],d['severity']) for d in v.get('diagnostics',v.get('issues',[]))) if isinstance(v,dict) else '')
print({k:(v[k] if not isinstance(v[k],(list,dict)) else '...') for k in v})
