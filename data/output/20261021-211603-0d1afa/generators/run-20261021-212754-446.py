import json
v=json.load(open('output/nightfang/review/validation.json'))
print(v.keys())
def walk(d,depth=0,key=''):
    if isinstance(d,dict):
        for k,x in d.items():
            if k in('groups','components','overlaps','collisions','warnings','diagnostics'):
                print(key+'/'+k, str(x)[:1500])
            else: walk(x,depth+1,key+'/'+k)
walk(v)