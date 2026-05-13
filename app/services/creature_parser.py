"""Tolerant homebrewery-style stat-block metadata parser.

AI Helper Docstring
Purpose: Best-effort extraction of creature metadata (name / size / type / CR) from a free-form homebrewery-style `body_md`. Real-world stat blocks (e.g. Freki in `examples/Torak Vermil.json`) deviate from our seed template — different italic flourishes, abbreviated CR, A5e-flavoured "Heroic" prefixes — so the parser is tolerant and only returns what it could match against the canonical lists.
Interactions:
- `app.api.creature_routes`: `POST /api/creatures/{id}/parse` calls `parse_stat_block` and returns the diff to the client.
- `app.schemas.char_sheet_global.{CREATURE_TYPES, CREATURE_SIZES}`: canonical taxonomy used for case-insensitive matching.

The parser does **not** mutate the body or invent values it can't find;
the route layer merges the returned dict onto the existing creature so
unmatched fields are left untouched. Caller decides whether to overwrite.
"""

from __future__ import annotations

import re

from app.schemas.char_sheet_global import CREATURE_SIZES, CREATURE_TYPES


# Strip a leading blockquote marker (`> ` or just `>`) and whitespace from a line.
# Homebrewery stat blocks are wrapped in `> ` quotes; the canonical headings
# (`> ## Name`, `> *Size, Type*`, `> *Challenge* ...`) live inside.
_QUOTE_PREFIX = re.compile(r"^\s*>?\s*")

# Italic-only line — `*text*` (or `**text**`) with no other content. Matches
# the size/type line directly under the name in the template, even when
# wrapped in `> `. Accepts one or two asterisks so we match both the SRD
# (`*Tiny beast*`) and bolded variants some homebrews use.
_ITALIC_LINE = re.compile(r"^\*{1,2}([^*][^*]*?)\*{1,2}\s*$")

# Heading lines. We accept H1 / H2 / H3 / H4; the template uses H2 (`## Name`),
# the SRD style guide tends toward H1. Order in the file wins.
_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")

# `*Challenge* 1/8 (25 XP)` or `**Challenge** 1 (200 XP)` — capture the token
# after the field name. Tolerant to single- or double-asterisks (italic vs
# bold), extra spaces, and the dagger/emsp glyphs upstream homebrewery uses.
_CHALLENGE = re.compile(r"\*+\s*Challenge\s*\*+\s*([^\s(*]+)", re.IGNORECASE)

# Splits a size/type italic line into its non-comma tokens. We also split on
# `/` so compound creature types like `aberration/undead` resolve to two
# separate tokens.
_TOKEN_SPLIT = re.compile(r"[,\s/]+")


def _strip_quote(line: str) -> str:
    """Return `line` with any leading `> ` blockquote marker stripped."""
    return _QUOTE_PREFIX.sub("", line, count=1).rstrip()


def parse_stat_block(body_md: str) -> dict[str, str]:
    """Extract `name`, `size`, `creature_type`, `challenge_rating` from a stat block.

    Returns only keys the parser could populate — never invents values. Caller
    merges onto the existing row. Habitat is intentionally not parsed; stat
    blocks rarely carry it, and the catalog defaults to "Any".
    """
    if not body_md or not body_md.strip():
        return {}

    out: dict[str, str] = {}
    lines = [_strip_quote(line) for line in body_md.splitlines()]

    # Walk the body looking for the first heading and the italic line that
    # follows it (skipping blank / divider lines). That's where the canonical
    # template puts name + size/type.
    name_idx: int | None = None
    for idx, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and m.group(2).strip():
            out["name"] = m.group(2).strip()
            name_idx = idx
            break

    if name_idx is not None:
        # Scan the next handful of lines for the size/type italic.
        for follow in lines[name_idx + 1 : name_idx + 6]:
            stripped = follow.strip()
            if not stripped or set(stripped) <= {"_", "-", "*"}:
                continue  # divider rule
            m = _ITALIC_LINE.match(stripped)
            if not m:
                # Allow `*Heroic Medium Beast*` with trailing whitespace already
                # eaten by rstrip; if it doesn't match, give up after the first
                # non-blank non-divider line so we don't grab `*Armor Class*`.
                break
            _extract_size_and_type(m.group(1), out)
            break

    # Challenge can appear anywhere; one match wins.
    cr_match = _CHALLENGE.search(body_md)
    if cr_match:
        out["challenge_rating"] = cr_match.group(1).strip().rstrip("(").strip()

    return out


def _extract_size_and_type(italic_text: str, out: dict[str, str]) -> None:
    """Walk tokens in the size/type italic line. First canonical size wins;
    every canonical type found is collected (deduplicated, order preserved)."""
    sizes_lc = {s.lower(): s for s in CREATURE_SIZES}
    types_lc = {t.lower(): t for t in CREATURE_TYPES}

    found_size: str | None = None
    found_types: list[str] = []
    for raw in _TOKEN_SPLIT.split(italic_text):
        tok = raw.strip().strip(".,").lower()
        if not tok:
            continue
        if found_size is None and tok in sizes_lc:
            found_size = sizes_lc[tok]
            continue
        # Tolerate plural-s forms like "aberrations" → "Aberration" — common
        # in "swarm of <type>s" stat blocks.
        singular = tok[:-1] if tok.endswith("s") else tok
        if tok in types_lc:
            canonical = types_lc[tok]
        elif singular in types_lc:
            canonical = types_lc[singular]
        else:
            continue
        if canonical not in found_types:
            found_types.append(canonical)

    if found_size:
        out["size"] = found_size
    if found_types:
        out["creature_type"] = ", ".join(found_types)
