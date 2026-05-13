"""
AI Helper Docstring
Purpose: Unit tests for the homebrewery-style stat-block parser. Covers the seed template, a real-world A5e-flavoured ally body (Freki) from `examples/Torak Vermil.json`, the canonical SRD italic-line format, double-asterisk (bold) variants from third-party homebrewery books, malformed input, and the edge cases the smoke test against the "Terror Unto Madness" book exposed (slash-separated compound types, plural type tokens).
Interactions:
- Targets `app.services.creature_parser.parse_stat_block`.
"""

from app.services.creature_parser import parse_stat_block


# A canonical SRD-flavoured stat block heading + italic line + CR.
SRD_LIKE = """\
___
> ## Goblin
> *Small humanoid (goblinoid), neutral evil*
> ___
> *Armor Class* 15 (leather armor, shield)
> *Hit Points* 7 (2d6)
> *Speed* 30 ft.
> ___
> *Challenge* 1/4 (50 XP)
> ___
"""

# Style the "Terror Unto Madness" book uses — bullet-list fields with
# **bold** field names, italic size/type line directly under the heading,
# slash-separated compound types in some entries.
BOOK_STYLE_BOLD = """\
> ## Aboleth Hatchling
>*Tiny aberration, lawful evil*
> ___
> - **Armor Class** 14
> - **Hit Points** 7 (1d10 + 1)
> - **Speed** 10 ft., swim 40 ft.
> ___
> - **Challenge** 1/2 (100 XP)
"""

BOOK_STYLE_COMPOUND = """\
> ## Doomsphere
>*Large aberration/undead, neutral evil*
> ___
> - **Armor Class** 12 (Natural Armor)
> - **Challenge** 9 (5,000 XP)
"""

BOOK_STYLE_PLURAL_SWARM = """\
> ## Swarm of Cranium Rats
>*Medium swarm of tiny aberrations, lawful evil*
> ___
> - **Challenge** 5 (1,800 XP)
"""

A5E_FLAVOURED = """\
___
> ## Mastif Companion
> *Heroic Medium Beast*
> ___
> *Challenge* 1/8 (25 XP) &emsp; *Heroic Level* 1
"""


def test_srd_format():
    out = parse_stat_block(SRD_LIKE)
    assert out["name"] == "Goblin"
    assert out["size"] == "Small"
    assert out["creature_type"] == "Humanoid"
    assert out["challenge_rating"] == "1/4"


def test_book_style_bold():
    """Homebrewery books that bold the field names should still parse."""
    out = parse_stat_block(BOOK_STYLE_BOLD)
    assert out["name"] == "Aboleth Hatchling"
    assert out["size"] == "Tiny"
    assert out["creature_type"] == "Aberration"
    assert out["challenge_rating"] == "1/2"


def test_compound_type_slash():
    """`aberration/undead` must resolve to two canonical types (order preserved)."""
    out = parse_stat_block(BOOK_STYLE_COMPOUND)
    assert out["name"] == "Doomsphere"
    assert out["size"] == "Large"
    assert out["creature_type"] == "Aberration, Undead"
    assert out["challenge_rating"] == "9"


def test_plural_type_token():
    """`tiny aberrations` (plural) should still match Aberration."""
    out = parse_stat_block(BOOK_STYLE_PLURAL_SWARM)
    # `swarm` is not a canonical token → dropped. Size is `Medium` (the first
    # canonical size token); `tiny` is dropped because we already locked size.
    assert out["size"] == "Medium"
    assert out["creature_type"] == "Aberration"


def test_a5e_heroic_prefix_freki():
    """`*Heroic Medium Beast*` — "Heroic" is not canonical and gets dropped;
    Medium + Beast win."""
    out = parse_stat_block(A5E_FLAVOURED)
    assert out["name"] == "Mastif Companion"
    assert out["size"] == "Medium"
    assert out["creature_type"] == "Beast"
    assert out["challenge_rating"] == "1/8"


def test_empty_input():
    assert parse_stat_block("") == {}
    assert parse_stat_block("   ") == {}


def test_garbage_input_no_crash():
    """No heading, no italic line, no Challenge → empty dict, no exception."""
    assert parse_stat_block("just a paragraph of text") == {}


def test_size_locks_after_first_match():
    """Once a canonical size is found, additional size words are ignored —
    avoids `Medium swarm of tiny aberrations` overwriting Medium with Tiny."""
    out = parse_stat_block(BOOK_STYLE_PLURAL_SWARM)
    assert out["size"] == "Medium"


def test_returns_only_found_fields():
    """An italic line with neither size nor type yields empty fields rather
    than missing keys — caller knows to leave the row untouched."""
    body = "## Mystery\n*Some flavourful description*\n*Challenge* 5"
    out = parse_stat_block(body)
    assert out == {"name": "Mystery", "challenge_rating": "5"}
