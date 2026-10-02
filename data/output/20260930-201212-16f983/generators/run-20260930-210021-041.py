import json
from pathlib import Path
out=Path('output/prospect/shortlist')
res=json.load(open(out/'shortlist.json'))
lines=['0 FILE shortlist-board.ldr','0 Shortlist review board (not a model): candidate subassemblies on a grid','0 Name: shortlist-board.ldr','0 Author: LDraw Astra agent (review board; sources keep their own headers)','0 !LDRAW_ORG Model']
grid=[]
for i,r in enumerate(res):
    row,col=divmod(i,5)
    x,z=col*480-960,row*480-480
    lines.append(f'1 7 {x} 0 {z} 1 0 0 0 1 0 0 0 1 {r["root"]}')
    grid.append(dict(label=r['label'],row=row,col=col,x=x,z=z))
lines.append('0 NOFILE')
body='\r\n'.join(lines)+'\r\n'
for r in res:
    body+=Path(out/f"{r['ns']}.mpd").read_text(encoding='utf-8-sig').replace('\r\n','\n').replace('\n','\r\n')
Path(out/'shortlist-board.mpd').write_text(body,encoding='utf-8',newline='')
json.dump(grid,open(out/'board-grid.json','w'),indent=1)
for g in grid: print(g['row'],g['col'],g['label'])