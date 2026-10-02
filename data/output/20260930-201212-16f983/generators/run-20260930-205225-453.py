import sys; sys.path.insert(0,'.')
from ldraw_tools.document import parse_source, section_table, is_part
from ldraw_tools.common import get_parts
from ldraw import Piece
m = parse_source('data/models-annotated/8865-1.mpd')
print(type(m), [a for a in dir(m) if not a.startswith('_')][:40])
p = next(o for o in m.objects if isinstance(o, Piece)) if hasattr(m,'objects') else None
sec = list(section_table(m).values())[1]
p = next(o for o in sec.pieces)
print([a for a in dir(p) if not a.startswith('_')])
print(p.reference, p.colour, p.position, p.matrix)
print(len(sec.steps), type(sec.steps[0]))
parts = get_parts()
print(type(parts.by_code), list(parts.by_code.items())[:2])