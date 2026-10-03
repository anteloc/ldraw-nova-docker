
from pyldraw3 import LDrawDocument
import json

lib = "/opt/ldraw/ldraw"
doc = LDrawDocument.load(lib + "/3001.dat") if False else None

# Use the toolkit's document handling if available; otherwise parse minimal bounds
import pyldraw3 as pl
print([n for n in dir(pl) if not n.startswith('_')])
