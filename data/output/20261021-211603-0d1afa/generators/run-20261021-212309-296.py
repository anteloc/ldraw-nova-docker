import sys; sys.path.insert(0,'.')
from ldraw_tools.common import get_parts
parts=get_parts()
for p in ['6141','2412b','3010','3004','3040b','3037','4286','3298','3297','3039','4287','3665','3034','3795','69729','87079','3023','3069b','3070b','2431','3710','3666','11477','15068','93273','4871','4081b','3043','98138','3068b','6636','4162','3022','3024','3020']:
    try:
        g=parts.geometry(p)
        print(p,parts.by_code.get(p),[round(x) for x in g.bounds.min] if hasattr(g.bounds,'min') else g.bounds, [round(x) for x in g.bounds.max] if hasattr(g.bounds,'max') else '')
    except Exception as e: print(p,'ERR',e)