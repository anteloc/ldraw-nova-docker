import sys; sys.path.insert(0,'output/generators')
import fz
for r in ['32449','6632','2780','6558','43093','11214','3705','3673','32523','41239','40490','32525','32009','15100','55615','6536','63869','42003','32184','32054','3648','73129','4255','4254','22977','731','32181c02','76138','2909']:
    try:
        lo,hi=fz.bounds(r); print(r, fz.desc(r)[:48], lo.round(1).tolist(), hi.round(1).tolist())
    except Exception as e: print(r,'ERR',e)
