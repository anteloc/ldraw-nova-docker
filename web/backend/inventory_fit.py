"""Bounded, quantity-aware recoloring and exact-footprint brick/plate splitting.

Run with the toolkit Python. Keep model parsing and occurrence expansion in Nova.
"""

from __future__ import annotations
from collections import Counter
import json
import math
from pathlib import Path
import re
import sys

MAX_PARTS = 5000
MAX_SEARCH = 2000
MAX_TOTAL_SEARCH = 20000


def fit(placements, lots, profiles, rgb):
    stock = Counter()
    for lot in lots:
        if (
            type(lot.get("color")) is not int
            or type(lot.get("quantity")) is not int
            or not 1 <= lot["quantity"] <= 1000000
        ):
            raise ValueError("Invalid owned inventory quantities")
        if not re.fullmatch(r"[a-z0-9_-]{1,80}", lot.get("part", "")):
            raise ValueError("Invalid owned part number")
        stock[(lot["part"], lot["color"])] += lot["quantity"]
    if len(placements) > MAX_PARTS:
        raise ValueError("Fit at most 5,000 physical parts at a time")
    remaining = []
    output = [None] * len(placements)
    changes = []

    def distance(a, b):
        if a == b:
            return 0
        if a not in rgb or b not in rgb:
            return 1000000
        return sum((x - y) ** 2 for x, y in zip(rgb[a], rgb[b]))

    # Reserve every exact match before any approximate choice can spend it.
    for i, p in enumerate(placements):
        key = (p["part"], p["color"])
        if stock[key] > 0:
            stock[key] -= 1
            output[i] = [p]
        else:
            remaining.append(i)
    for i in remaining:
        p = placements[i]
        options = [k for k, q in stock.items() if q > 0 and k[0] == p["part"]]
        if options:
            key = min(options, key=lambda k: (distance(p["color"], k[1]), k))
            stock[key] -= 1
            output[i] = [{**p, "color": key[1]}]
            changes.append(
                {"index": i, "kind": "color", "from": p["color"], "to": key[1]}
            )
    missing = []
    total_visits = 0
    for i in remaining:
        if output[i] is not None:
            continue
        p = placements[i]
        profile = profiles.get(p["part"])
        # Split only known plain studded bricks/plates. Do not infer shape
        # equivalence for Technic, hinges, tiles, prints, wedges or custom parts.
        if (
            profile
            and profile["studs"]
            and profile["description"].lstrip().startswith(("Brick ", "Plate "))
        ):
            width, depth = profile["x_studs"], profile["z_studs"]
            if width * depth <= 64:
                candidates = []
                for (part, color), quantity in stock.items():
                    alt = profiles.get(part)
                    if (
                        quantity <= 0
                        or not alt
                        or not alt["studs"]
                        or alt["height"] != profile["height"]
                    ):
                        continue
                    if not alt["description"].lstrip().startswith(("Brick ", "Plate ")):
                        continue
                    for rotation in (False, True):
                        w, d = (
                            (alt["z_studs"], alt["x_studs"])
                            if rotation
                            else (alt["x_studs"], alt["z_studs"])
                        )
                        if w <= width and d <= depth:
                            candidates.append((part, color, w, d, rotation))
                candidates.sort(
                    key=lambda c: (distance(p["color"], c[1]), -c[2] * c[3], c)
                )
                candidates = candidates[:128]
                all_cells = {(x, z) for x in range(width) for z in range(depth)}
                visits = 0

                def cover(cells, chosen):
                    nonlocal visits, total_visits
                    visits += 1
                    total_visits += 1
                    if visits > MAX_SEARCH or total_visits > MAX_TOTAL_SEARCH:
                        return None
                    if not cells:
                        return chosen
                    x, z = min(cells)
                    for part, color, w, d, rotation in candidates:
                        key = (part, color)
                        if stock[key] <= 0:
                            continue
                        region = {
                            (x + dx, z + dz) for dx in range(w) for dz in range(d)
                        }
                        if not region <= cells:
                            continue
                        stock[key] -= 1
                        found = cover(
                            cells - region,
                            [*chosen, (part, color, w, d, rotation, x, z)],
                        )
                        if found is not None:
                            return found
                        stock[key] += 1
                    return None

                chosen = (
                    cover(all_cells, [])
                    if candidates and total_visits < MAX_TOTAL_SEARCH
                    else None
                )
                if chosen:
                    output[i] = [
                        {
                            **p,
                            "part": part,
                            "color": color,
                            "offset": [
                                -width * 10 + x * 20 + w * 10,
                                0,
                                -depth * 10 + z * 20 + d * 10,
                            ],
                            "rotated": rotation,
                        }
                        for part, color, w, d, rotation, x, z in chosen
                    ]
                    changes.append(
                        {
                            "index": i,
                            "kind": "split",
                            "from": p["part"],
                            "to": [{"part": v[0], "color": v[1]} for v in chosen],
                        }
                    )
        if output[i] is None:
            output[i] = [p]
            missing.append((p["part"], p["color"]))
    flattened = [p for group in output for p in group]
    if len(flattened) > 10000:
        raise ValueError("Fitted model exceeds 10,000 physical parts")
    shortages = Counter(missing)
    report = {
        "total_parts": len(flattened),
        "matched_parts": len(flattened) - len(missing),
        "missing_parts": len(missing),
        "color_changes": sum(c["kind"] == "color" for c in changes),
        "splits": sum(c["kind"] == "split" for c in changes),
        "changes": changes,
        "missing": [
            {"part": p, "color": c, "quantity": q}
            for (p, c), q in sorted(shortages.items())
        ],
        "strategy": "Exact matches first, closest available color, bounded exact-footprint splits; best effort, not a global optimum.",
    }
    return flattened, report


def run(source, snapshot, output, report_path, library):
    import numpy as np
    from ldraw_tools.document import (
        parse_source,
        physical_context,
        section_table,
        is_part,
    )
    from ldraw_tools.common import get_parts, jsonable, atomic_write, DATA
    from ldraw_tools.validation import validate_text

    model = parse_source(source)
    # Reject semantics a flattened physical-parts export cannot preserve.
    for section in section_table(model).values():
        if not is_part(section) and any(
            line.split()[:1] in (["2"], ["3"], ["4"], ["5"])
            or any(
                tag in line
                for tag in ("!TEXMAP", "!DATA", "BFC INVERTNEXT", "!COLOUR", "ROTSTEP")
            )
            for line in section.to_ldraw().splitlines()
        ):
            raise ValueError(
                "This model uses custom geometry or transform metadata. Ask Nova to redesign it with standard parts before fitting."
            )
    parts = get_parts(library)
    view, _ = physical_context(model, parts)
    placements = []
    for occ in view.iter_occurrences(include_steps=True):
        if len(placements) >= MAX_PARTS:
            raise ValueError("Fit at most 5,000 physical parts at a time")
        code = str(occ.colour.code)
        if not code.isdigit() or int(code) in (16, 24):
            raise ValueError("Use explicit colors before fitting this model")
        placements.append(
            {
                "part": occ.part_code.lower().removesuffix(".dat"),
                "color": int(code),
                "position": jsonable(occ.position),
                "matrix": jsonable(occ.matrix),
                "step": occ.step,
            }
        )
    if not placements:
        raise ValueError("No physical parts to fit")
    owned = json.loads(Path(snapshot).read_text())
    rgb = {}
    for line in (Path(library) / "LDConfig.ldr").read_text().splitlines():
        m = re.match(
            r"0\s+!COLOUR\s+\S+\s+CODE\s+(\d+)\s+VALUE\s+#([A-Fa-f0-9]{6})", line
        )
        if m:
            rgb[int(m[1])] = [int(m[2][j : j + 2], 16) for j in (0, 2, 4)]
    profile = json.loads((DATA / "rectangular-parts.json").read_text())["parts"]
    fitted, report = fit(placements, owned["lots"], profile, rgb)
    lines = [
        "0 FILE owned-parts.ldr",
        "0 Model fitted to owned parts",
        "0 Name: owned-parts.ldr",
        "0 !LDRAW_ORG Model",
    ]
    original = Path(source).read_text().splitlines()
    for prefix in ("0 Author:", "0 !LICENSE"):
        retained = next((line for line in original if line.startswith(prefix)), None)
        if retained:
            lines.append(retained)
    lines.append("0 // Adapted by LDraw Nova; original author and license retained.")
    previous = None
    for p in fitted:
        if previous is not None and p["step"] != previous:
            lines.append("0 STEP")
        previous = p["step"]
        matrix = np.array(p["matrix"])
        position = np.array(p["position"])
        if "offset" in p:
            position = position + matrix @ np.array(p["offset"])
            if p["rotated"]:
                matrix = matrix @ np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
        numbers = [*position, *matrix.flatten()]
        if not all(math.isfinite(float(n)) for n in numbers):
            raise ValueError("Nonfinite placement")
        lines.append(
            "1 "
            + str(p["color"])
            + " "
            + " ".join(f"{n:.9g}" for n in numbers)
            + " "
            + p["part"]
            + ".dat"
        )
    for section in section_table(model).values():
        if is_part(section):
            lines.extend(["0 FILE " + section.name, section.to_ldraw()])
    text = "\r\n".join(lines) + "\r\n"
    _, diagnostics = validate_text(text, parts, assembly=True, instance_limit=10000)
    errors = [d for d in diagnostics if str(d.get("severity")) == "error"]
    if errors:
        raise ValueError(
            "Fitted placements failed Nova structural validation: "
            + "; ".join(d["code"] + ": " + d["message"] for d in errors)[:2000]
        )
    atomic_write(output, text)
    report["inventory_revision"] = owned["revision"]
    atomic_write(report_path, json.dumps(report))


if __name__ == "__main__":
    try:
        run(*sys.argv[1:])
    except Exception as exc:
        print("Parts fitting failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
