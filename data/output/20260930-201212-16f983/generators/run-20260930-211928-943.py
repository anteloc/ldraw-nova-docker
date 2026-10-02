import json, collections
d=json.load(open('output/phase3/donor/d39-rear-s21.inspect.json'))
c=collections.Counter((x['code'],x['severity']) for x in d['diagnostics']); print(c.most_common(10))
print([x for x in d['diagnostics'] if x['severity']=='error' and x['code']!='coverage.raw_geometry'][:3])
