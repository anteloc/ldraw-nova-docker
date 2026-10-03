import sys
sys.path.insert(0, "/data/chats/20261003-100404-9e6e55/workspace/.venv/lib/python3.14/site-packages")
import ldraw
print("ldraw ok:", ldraw.__file__, getattr(ldraw, "__version__", "?"))
import inspect
names = [n for n in dir(ldraw) if not n.startswith('_')]
print(names[:40])
