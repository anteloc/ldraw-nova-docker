import sys
sys.path.insert(0, "/data/chats/20261003-100404-9e6e55/workspace/.venv/lib/python3.14/site-packages")
import ldraw as pl, inspect
print(inspect.signature(pl.model))
print(inspect.getdoc(pl.model)[:400])
