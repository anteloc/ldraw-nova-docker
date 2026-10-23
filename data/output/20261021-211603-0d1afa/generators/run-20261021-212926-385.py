import sys; sys.path.insert(0,'.')
from ldraw_tools.common import get_parts
P=get_parts()
for c in ['3829c01','3039','3022']:
    g=P.geometry(c); print(c,g.bounds.min,g.bounds.max)
import subprocess,json
d=json.loads(subprocess.run(['./ldraw-agent','part','3829c01','--limit','10'],capture_output=True,text=True).stdout)
for c in d['connectors']: print(c['kind'],c['position'],c['frame'][1])