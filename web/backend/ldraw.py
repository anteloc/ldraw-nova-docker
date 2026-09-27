"""LDraw knowledge for the agent tools: part search, colours, validation."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

import settings
from build_index import index_parts

# Where type-1 references can resolve inside the parts library.
LIBRARY_SUBDIRS = ("parts", "p", "models")


# --- indexes ---------------------------------------------------------------

@lru_cache(maxsize=1)
def parts_index() -> list[list[str]]:
    path = settings.INDEX_DIR / "parts.json"
    if path.exists():
        return json.loads(path.read_text())
    return index_parts(settings.LDRAW_DIR)            # dev fallback: slow, no cache file


@lru_cache(maxsize=1)
def library_ids() -> frozenset[str]:
    """Every id a type-1 line can reference: '3001.dat', 's/3001s01.dat', '48/1-4cyli.dat', ..."""
    ids = set()
    for sub in LIBRARY_SUBDIRS:
        root = settings.LDRAW_DIR / sub
        for dirpath, _dirs, files in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root)
            for name in files:
                rel = name if rel_dir == "." else f"{rel_dir}/{name}"
                ids.add(rel.lower())
    return frozenset(ids)


@lru_cache(maxsize=1)
def colours() -> dict[int, str]:
    """LDConfig colour code -> name."""
    result = {}
    ldconfig = next((p for p in settings.LDRAW_DIR.iterdir() if p.name.lower() == "ldconfig.ldr"), None)
    if ldconfig is None:
        return result
    for line in ldconfig.read_text(errors="replace").splitlines():
        words = line.split()
        if len(words) >= 5 and words[:2] == ["0", "!COLOUR"] and words[3] == "CODE":
            result[int(words[4])] = words[2]
    return result


# --- search ----------------------------------------------------------------

def _normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"(\d)\s*x\s*(?=\d)", r"\1 x ", text)   # "2x4" / "2 x  4" -> "2 x 4"
    return " ".join(text.split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9./]+", _normalise(text))


def find_parts(query: str, limit: int = 20) -> list[dict]:
    q_norm, q_words = _normalise(query), _words(query)
    if not q_words:
        return []
    scored = []
    for pid, description, category, keywords, part_type in parts_index():
        if description.startswith("~Moved to"):
            continue
        desc_norm = _normalise(description)
        haystack = f"{pid} {desc_norm} {keywords.lower()}"
        hay_words = set(_words(haystack))
        if not all(w in hay_words or w in haystack for w in q_words):
            continue
        score = 0.0
        if q_norm == pid or q_norm == pid.removesuffix(".dat"):
            score += 100
        if q_norm in desc_norm:
            score += 20
            if desc_norm.startswith(q_norm):
                score += 10
        score -= len(desc_norm) / 40                       # prefer plain, short descriptions
        if description.startswith(("~", "_", "=", "|")):   # sub-assemblies, colour/alias variants
            score -= 15
        if part_type == "Shortcut":
            score -= 3
        if re.search(r"p[a-z0-9]{2,}\.dat$", pid):          # printed/patterned variants
            score -= 4
        scored.append((score, pid, description, category))
    scored.sort(key=lambda row: -row[0])
    return [{"id": pid, "description": d, "category": c} for _s, pid, d, c in scored[:limit]]


# --- validation ------------------------------------------------------------

TITLE_SKIP = ("Name:", "Author:", "!", "FILE", "NOFILE", "//", "BFC", "STEP")


def title_of(lines: Iterable[str]) -> str:
    """A model's title (description), per the LDraw file format: the first line
    of a single-file model, or the line right after `0 FILE ...` in an MPD —
    i.e. line 2 of an .mpd. Blank lines are skipped."""
    lines = [line.strip() for line in lines if line.strip()]
    if not lines:
        return ""
    index = 1 if lines[0].split()[:2] == ["0", "FILE"] else 0
    if index >= len(lines):
        return ""
    words = lines[index].split(None, 1)
    if len(words) < 2 or words[0] != "0" or words[1].startswith(TITLE_SKIP):
        return ""
    return words[1].strip()


@dataclass
class Validation:
    content: str
    title: str = ""
    warnings: list[str] = field(default_factory=list)
    part_count: int = 0
    submodels: list[str] = field(default_factory=list)
    unknown_parts: dict[str, list[dict]] = field(default_factory=dict)


def _file_name(line: str) -> str:
    return line.split("FILE", 1)[1].strip()


def _ref_id(name: str) -> str:
    return name.strip().lower().replace("\\", "/")


def validate_model(content: str, main_name: str, description: Optional[str] = None) -> Validation:
    """Normalise and sanity-check an LDraw model. Problems become warnings for
    the agent to act on, not hard errors: LeoCAD will still try to render it.

    The result always starts with `0 FILE <name>`; with `description`, a title
    line is added right after it (line 2) unless the model already has one."""
    content = content.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or not lines[0].startswith("0 FILE"):
        lines.insert(0, f"0 FILE {main_name}")
    if description and not title_of(lines[:3]):
        lines.insert(1, "0 " + " ".join(description.split()))
    content = "\n".join(lines)
    if not content.endswith("\n"):
        content += "\n"

    result = Validation(content=content, title=title_of(lines[:3]))
    local_files = {_ref_id(_file_name(l)) for l in lines if l.startswith("0 FILE")}
    result.submodels = [_file_name(l) for l in lines if l.startswith("0 FILE")]
    known_ids, known_colours = library_ids(), colours()
    bad_colours: set[str] = set()

    for number, line in enumerate(lines, start=1):
        words = line.split()
        if not words or words[0] == "0":
            continue
        kind = words[0]
        expected = {"1": 15, "2": 8, "3": 11, "4": 14, "5": 14}.get(kind)
        if expected is None:
            result.warnings.append(f"line {number}: unknown line type {kind!r}")
            continue
        if len(words) < expected:
            result.warnings.append(f"line {number}: type {kind} line needs {expected} fields, got {len(words)}")
            continue
        colour = words[1]
        if not colour.lower().startswith("0x2"):
            try:
                if int(colour) not in known_colours and int(colour) not in (16, 24):
                    bad_colours.add(colour)
            except ValueError:
                result.warnings.append(f"line {number}: colour {colour!r} is not a number")
        numbers = words[2:14] if kind == "1" else words[2:expected]
        try:
            [float(n) for n in numbers]
        except ValueError:
            result.warnings.append(f"line {number}: non-numeric coordinates/matrix")
            continue
        if kind == "1":
            result.part_count += 1
            # The file name is everything after the 14th field and may contain spaces.
            ref = _ref_id(line.split(None, 14)[14])
            if ref not in local_files and ref not in known_ids and ref not in result.unknown_parts:
                stem = ref.rsplit("/", 1)[-1].removesuffix(".dat").removesuffix(".ldr")
                result.unknown_parts[ref] = find_parts(stem, limit=3)

    if bad_colours:
        result.warnings.append(f"unknown colour codes (not in LDConfig.ldr): {', '.join(sorted(bad_colours))}")
    for ref, suggestions in result.unknown_parts.items():
        hint = "; ".join(f'{s["id"]} ({s["description"]})' for s in suggestions) or "no close matches"
        result.warnings.append(f"unknown part/submodel {ref!r} — not in the library or this file. Similar: {hint}")
    if result.part_count == 0:
        result.warnings.append("the model contains no parts (no type-1 lines)")
    return result
