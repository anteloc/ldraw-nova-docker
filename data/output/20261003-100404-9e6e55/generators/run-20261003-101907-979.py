import sys
sys.path.insert(0, "/data/chats/20261003-100404-9e6e55/workspace/.venv/lib/python3.14/site-packages")
import ldraw as pl
# find a way to load parts and get bounds
doc = pl.LDrawDocument() if hasattr(pl, 'LDrawDocument') else None
print("LDrawDocument" in dir(pl))
print([n for n in dir(pl) if 'ound' in n or 'Doc' in n or 'odel' in n][:30])
