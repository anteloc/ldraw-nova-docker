import json,collections
R=json.load(open('output/prospect/census.json'))
agg=collections.defaultdict(collections.Counter)
for car in R:
    for u in car['units']:
        for tag,parts in u['signature_parts'].items():
            for k,n in parts.items(): agg[tag][k]+=n
for tag in ['differential','engine','gearbox','steering_rack','knuckle_hub','suspension','cv_ujoint','steering_input','seat','door','windscreen']:
    print('==',tag)
    for k,n in agg[tag].most_common(10): print('  ',n,k[:95])