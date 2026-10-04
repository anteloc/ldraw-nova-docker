"""Atomically indexed public set inventories; no API key or ownership sharing."""

from __future__ import annotations
from contextlib import closing
import csv
import gzip
import html
import io
import re
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import httpx
import owned_parts

FILES = (
    "sets",
    "parts",
    "colors",
    "inventories",
    "inventory_parts",
    "inventory_sets",
    "inventory_minifigs",
)
HOSTS = {
    "cdn.rebrickable.com",
    "www.bricklink.com",
    "bricklink.com",
    "v2.bricklink.com",
    "www.lego.com",
    "lego.com",
    "raw.githubusercontent.com",
}
BRICKLINK_BASIC = {
    "1": 15,
    "2": 19,
    "3": 14,
    "4": 25,
    "5": 4,
    "6": 2,
    "7": 1,
    "8": 6,
    "9": 7,
    "10": 8,
    "11": 0,
    "85": 72,
    "86": 71,
    "88": 70,
}


def path():
    return owned_parts.directory() / "catalog.sqlite"


def safe_url(url):
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or p.hostname not in HOSTS
        or p.username
        or p.password
        or p.port not in (None, 443)
        or len(url) > 2048
        or p.fragment
    ):
        raise ValueError(
            "Use an HTTPS LEGO/BrickLink set link or a public CSV/XML export from LEGO, BrickLink, Rebrickable or raw.githubusercontent.com"
        )
    return url


def download(url, limit):
    import ipaddress, socket

    safe_url(url)
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            host = urlsplit(url).hostname
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            if not addresses or any(
                not ipaddress.ip_address(a[4][0]).is_global for a in addresses
            ):
                raise ValueError("The source must use a public catalog host")
            with client.stream(
                "GET", url, headers={"User-Agent": "LDrawNova/1.0 parts-import"}
            ) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin

                    url = safe_url(urljoin(url, response.headers.get("location", "")))
                    continue
                if response.status_code in (401, 403):
                    raise ValueError(
                        "This source requires sign-in. Download its CSV/XML export in your browser and upload it instead."
                    )
                response.raise_for_status()
                result = bytearray()
                for block in response.iter_bytes():
                    result.extend(block)
                    if len(result) > limit:
                        raise ValueError("Catalog response exceeds its size limit")
                return bytes(result)
    raise ValueError("Too many catalog redirects")


def set_number(value):
    value = value.strip()
    if "://" in value:
        safe_url(value)
        p = urlsplit(value)
        if p.hostname in ("www.lego.com", "lego.com"):
            m = re.search(
                r"(?:building-?instructions/|product/[^/]*?)(\d{3,7})(?:/)?$", p.path
            )
            if not m:
                raise ValueError(
                    "Use a LEGO product or building-instructions link with a set number"
                )
            value = m[1]
        elif p.hostname in ("www.bricklink.com", "bricklink.com", "v2.bricklink.com"):
            query = parse_qs(p.query)
            value = (query.get("S") or query.get("itemNo") or [""])[0]
            if not value:
                m = re.search(r"/set/(\d{3,7}(?:-\d{1,3})?)/?$", p.path)
                value = m[1] if m else ""
        else:
            return None
    if not re.fullmatch(r"\d{3,7}(?:-\d{1,3})?", value):
        return None
    return value if "-" in value else value + "-1"


def csv_rows(raw):
    # Stream expanded CSV and bound compression bombs, lines and total expansion.
    total = 0
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as zipped:

        def lines():
            nonlocal total
            for line in zipped:
                total += len(line)
                if total > 512 * 1024 * 1024 or len(line) > 16384:
                    raise ValueError("Expanded catalog exceeds its budget")
                yield line.decode("utf-8-sig")

        for count, row in enumerate(csv.DictReader(lines())):
            if count > 10000000:
                raise ValueError("Catalog exceeds 10 million rows")
            yield row


def build(progress=lambda text: None):
    root = owned_parts.directory()
    with tempfile.TemporaryDirectory(dir=root, prefix="catalog-") as folder:
        target = Path(folder) / "catalog.sqlite"
        with closing(sqlite3.connect(target)) as db, db:
            db.executescript("""CREATE TABLE sets (num TEXT PRIMARY KEY,name TEXT,year INTEGER,num_parts INTEGER);
                CREATE TABLE parts (id TEXT PRIMARY KEY,name TEXT);
                CREATE TABLE colors (system TEXT,id TEXT,ldraw INTEGER,PRIMARY KEY(system,id));
                CREATE TABLE inventories (id INTEGER PRIMARY KEY,version INTEGER,num TEXT);
                CREATE TABLE items (inventory INTEGER,part TEXT,color TEXT,quantity INTEGER);
                CREATE TABLE children (inventory INTEGER,num TEXT,quantity INTEGER);
                CREATE TABLE metadata (updated TEXT,warning TEXT);""")
            for name in FILES:
                progress("Indexing " + name.replace("_", " "))
                rows = csv_rows(
                    download(
                        "https://cdn.rebrickable.com/media/downloads/"
                        + name
                        + ".csv.gz",
                        32 * 1024 * 1024,
                    )
                )
                if name == "sets":
                    sql = "INSERT INTO sets VALUES (?,?,?,?)"
                    values = (
                        (r["set_num"], r["name"], int(r["year"]), int(r["num_parts"]))
                        for r in rows
                    )
                elif name == "parts":
                    sql = "INSERT INTO parts VALUES (?,?)"
                    values = ((r["part_num"], r["name"]) for r in rows)
                elif name == "colors":
                    sql = "INSERT INTO colors VALUES (?,?,?)"
                    values = (
                        ("rebrickable", r["id"], owned_parts.color_named(r["name"]))
                        for r in rows
                    )
                elif name == "inventories":
                    sql = "INSERT INTO inventories VALUES (?,?,?)"
                    values = (
                        (int(r["id"]), int(r["version"]), r["set_num"]) for r in rows
                    )
                elif name == "inventory_parts":
                    sql = "INSERT INTO items VALUES (?,?,?,?)"
                    values = (
                        (
                            int(r["inventory_id"]),
                            r["part_num"],
                            r["color_id"],
                            owned_parts.positive(r["quantity"]),
                        )
                        for r in rows
                        if r["is_spare"].casefold() == "false"
                    )
                else:
                    sql = "INSERT INTO children VALUES (?,?,?)"
                    values = (
                        (
                            int(r["inventory_id"]),
                            r.get("set_num") or r["fig_num"],
                            owned_parts.positive(r["quantity"]),
                        )
                        for r in rows
                    )
                db.executemany(sql, values)
            progress("Mapping BrickLink colors")
            # Use exact official color names, not numeric ID equality or nearest RGB.
            warning = None
            try:
                page = download(
                    "https://v2.bricklink.com/en-us/catalog/color-guide",
                    4 * 1024 * 1024,
                ).decode()
            except (httpx.HTTPError, ValueError, UnicodeError):
                page = ""
                warning = "BrickLink color guide was unavailable. Basic colors are mapped; map other imported lots manually."
            mapped = dict(BRICKLINK_BASIC)
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
                if len(cells) != 2:
                    continue
                text = html.unescape(re.sub("<[^>]*>", " ", cells[1])).replace(
                    "\xa0", " "
                )
                m = re.fullmatch(r"\s*(.*?)\s+(\d+)\s*", text)
                if m:
                    color = owned_parts.color_named(m[1])
                    if color is not None:
                        mapped[m[2]] = color
            db.executemany(
                "INSERT INTO colors VALUES (?,?,?)",
                [("bricklink", k, v) for k, v in mapped.items()],
            )
            progress("Building search indexes")
            db.executescript(
                "CREATE INDEX inventories_num ON inventories(num,version DESC); CREATE INDEX items_inventory ON items(inventory); CREATE INDEX children_inventory ON children(inventory);"
            )
            db.execute("INSERT INTO metadata VALUES (datetime('now'),?)", (warning,))
        target.replace(path())
    progress("Ready")


def status():
    if not path().is_file():
        return {"ready": False, "sets": 0, "updated": None}
    with closing(sqlite3.connect(path())) as db, db:
        return {
            "ready": True,
            "sets": db.execute("SELECT count(*) FROM sets").fetchone()[0],
            "updated": db.execute("SELECT updated FROM metadata").fetchone()[0],
            "warning": db.execute("SELECT warning FROM metadata").fetchone()[0],
        }


def search(query):
    if not path().is_file():
        return []
    words = query.strip().split()[:6]
    if not words:
        return []
    conditions = []
    params = []
    for w in words:
        conditions.append('(lower(name) LIKE ? ESCAPE "!" OR num LIKE ? ESCAPE "!")')
        escaped = w.casefold().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        params.extend(["%" + escaped + "%", "%" + escaped + "%"])
    with closing(sqlite3.connect(path())) as db, db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM sets WHERE "
            + " AND ".join(conditions)
            + " ORDER BY CASE WHEN num=? OR num=? THEN 0 ELSE 1 END,year DESC,num LIMIT 30",
            [*params, query.strip(), query.strip() + "-1"],
        ).fetchall()
    return [
        {
            **dict(r),
            "lego_url": "https://www.lego.com/en-us/service/building-instructions/"
            + r["num"].split("-")[0],
            "bricklink_url": "https://www.bricklink.com/v2/catalog/catalogitem.page?S="
            + r["num"],
        }
        for r in rows
    ]


def color_map(system):
    if not path().is_file():
        return BRICKLINK_BASIC if system == "bricklink" else {}
    with closing(sqlite3.connect(path())) as db, db:
        return dict(db.execute("SELECT id,ldraw FROM colors WHERE system=?", (system,)))


def color_id(system, value):
    return color_map(system).get(value)


def inventory(number, copies=1):
    from collections import Counter

    if not path().is_file():
        raise ValueError("Download the set catalog in My Parts first")
    copies = owned_parts.positive(copies)
    result = Counter()
    with closing(sqlite3.connect(path())) as db, db:

        def visit(num, multiplier, ancestors):
            if num in ancestors or len(ancestors) > 8:
                raise ValueError(
                    "Set inventory contains a cycle or too many nested sets"
                )
            inv = db.execute(
                "SELECT id FROM inventories WHERE num=? ORDER BY version DESC LIMIT 1",
                (num,),
            ).fetchone()
            if not inv:
                raise ValueError(
                    "No complete inventory for " + num + " in this catalog"
                )
            for part, color, qty in db.execute(
                "SELECT part,color,quantity FROM items WHERE inventory=?", (inv[0],)
            ):
                result[(part, color)] += qty * multiplier
            for child, qty in db.execute(
                "SELECT num,quantity FROM children WHERE inventory=?", (inv[0],)
            ):
                visit(child, qty * multiplier, (*ancestors, num))
            if (
                len(result) > owned_parts.MAX_LOTS
                or sum(result.values()) > owned_parts.MAX_QUANTITY
            ):
                raise ValueError("Set selection exceeds the owned inventory budget")

        visit(number, copies, ())
    return owned_parts.normalize(
        [{"part": p, "color": c, "quantity": q} for (p, c), q in result.items()],
        "rebrickable",
    )
