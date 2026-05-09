"""One-shot scoper: rewrite phb.standalone.css → phb.scoped.css under `.phb`.

The upstream homebrewery file is **not** scoped — it ships a bare-element
Eric Meyer reset and dozens of body-level rules (`body`, `ol,ul`, `table`,
`a`, `em`, …). Loading it globally would zero out borders/padding/font
sizes for the entire app. This script wraps every qualified selector
under a `.phb` ancestor so the rules only fire inside elements we tag.

Run once after `curl`-ing a fresh upstream `phb.standalone.css`:

    python app/static/vendor/homebrewery/scope_phb_css.py

Behaviour:
- `@font-face`, `@keyframes`, `@charset`, `@import`, `@namespace` → emit verbatim.
- `@page` → drop entirely (we never simulate printed pages).
- `@media` / `@supports` → recurse into the body, scope the inner rules.
- Qualified rule (`selectors { decls }`) → split selectors on top-level
  commas (string- and paren-aware), drop bare `html`/`body`/`:root`/`*`
  parts, prefix the rest with `.phb ` unless they already contain `.phb`.

The script has zero third-party deps so it runs from any clean checkout
without a venv setup.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "phb.standalone.css"
DEST = HERE / "phb.scoped.css"

PASSTHROUGH_AT_RULES = ("@font-face", "@keyframes", "@-webkit-keyframes",
                        "@-moz-keyframes", "@charset", "@import",
                        "@namespace")
DROP_AT_RULES = ("@page",)
RECURSIVE_AT_RULES = ("@media", "@supports", "@-webkit-keyframes",
                      "@-moz-keyframes", "@document")


def _split_top_level_commas(s: str) -> list[str]:
    """Split a selector list on commas that aren't inside () [] or strings."""
    out, buf, depth = [], [], 0
    quote = None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _scope_selector(selector: str) -> str | None:
    """Return the scoped form of a selector list, or None to drop the rule."""
    parts = _split_top_level_commas(selector)
    kept: list[str] = []
    for part in parts:
        p = part.strip()
        if not p:
            continue
        # Already scoped — keep as-is (no double-prefix).
        if ".phb" in p:
            kept.append(p)
            continue
        # Drop selectors that can never sit under a .phb ancestor.
        head = p.split()[0]
        if head in ("html", "body", ":root", "*"):
            continue
        kept.append(f".phb {p}")
    if not kept:
        return None
    return ", ".join(kept)


def _find_block(src: str, start: int) -> tuple[int, int]:
    """Given an opening `{` at index `start-1`, return the (start, end_after_close)
    indices for the matching brace, accounting for nested braces and strings."""
    depth = 1
    i = start
    quote = None
    while i < len(src):
        ch = src[i]
        if quote:
            if ch == quote and src[i - 1] != "\\":
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return start, i  # body slice is src[start:i]; close-brace at i
        i += 1
    raise ValueError(f"Unbalanced braces from offset {start}")


def _scope_block(src: str) -> str:
    """Walk a CSS block (or whole file) and return the scoped output."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        # Skip whitespace
        while i < n and src[i].isspace():
            out.append(src[i])
            i += 1
        if i >= n:
            break
        if src.startswith("/*", i):  # CSS comment
            end = src.find("*/", i + 2)
            if end == -1:
                out.append(src[i:])
                break
            out.append(src[i:end + 2])
            i = end + 2
            continue

        if src[i] == "@":
            # Find the at-rule name (until whitespace, '{' or ';')
            j = i + 1
            while j < n and src[j] not in " \t\r\n;{":
                j += 1
            name = src[i:j]
            # Find prelude end ('{' for block at-rules, ';' for statement at-rules)
            k = j
            quote = None
            while k < n:
                ch = src[k]
                if quote:
                    if ch == quote and src[k - 1] != "\\":
                        quote = None
                elif ch in ('"', "'"):
                    quote = ch
                elif ch in "{;":
                    break
                k += 1
            if k >= n:
                out.append(src[i:])
                break
            if src[k] == ";":
                # Statement at-rule (@charset, @import, @namespace, …) — emit verbatim.
                out.append(src[i:k + 1])
                i = k + 1
                continue
            # Block at-rule.
            prelude = src[i:k]  # includes name + whatever is between
            body_start, body_end = _find_block(src, k + 1)
            body = src[body_start:body_end]
            if name in DROP_AT_RULES:
                pass  # skip entirely
            elif name in PASSTHROUGH_AT_RULES:
                out.append(prelude)
                out.append("{")
                out.append(body)
                out.append("}")
            elif name in RECURSIVE_AT_RULES:
                out.append(prelude)
                out.append("{")
                out.append(_scope_block(body))
                out.append("}")
            else:
                # Unknown at-rule: emit verbatim and log so a manual diff
                # review catches it. Failing safe = leak through (rare and
                # visible) over silently dropping (invisible).
                print(f"[scope_phb_css] unknown at-rule {name!r} — emitting verbatim")
                out.append(prelude)
                out.append("{")
                out.append(body)
                out.append("}")
            i = body_end + 1
            continue

        # Qualified rule: selector { decls }
        # Find the next `{` that ends the selector (string-aware).
        k = i
        quote = None
        while k < n:
            ch = src[k]
            if quote:
                if ch == quote and src[k - 1] != "\\":
                    quote = None
            elif ch in ('"', "'"):
                quote = ch
            elif ch == "{":
                break
            k += 1
        if k >= n:
            out.append(src[i:])
            break
        selector = src[i:k]
        body_start, body_end = _find_block(src, k + 1)
        body = src[body_start:body_end]
        scoped = _scope_selector(selector)
        if scoped is not None:
            out.append(scoped)
            out.append("{")
            out.append(body)
            out.append("}")
        i = body_end + 1
    return "".join(out)


def main() -> None:
    raw = SOURCE.read_text(encoding="utf-8")
    scoped = _scope_block(raw)
    DEST.write_text(scoped, encoding="utf-8")
    print(f"[scope_phb_css] {SOURCE.name}: {len(raw):,} bytes")
    print(f"[scope_phb_css] {DEST.name}:    {len(scoped):,} bytes")


if __name__ == "__main__":
    main()
