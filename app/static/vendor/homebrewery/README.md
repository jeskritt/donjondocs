# homebrewery — phb.standalone.css

Vendored from <https://github.com/naturalcrit/homebrewery>.

- **Source file:** `phb.standalone.css` at the repo root.
- **Fetched at commit:** `180755998797` (2026-05-05).
- **License:** MIT — see `LICENSE` in this directory.

## What it is

`phb.standalone.css` is the upstream stylesheet from the homebrewery
project — a self-contained file that approximates the visual language of
the official 5e Player's Handbook. The file embeds its custom fonts
(Bookinsanity, Mr Eaves Small Caps, Scaly Sans, Scaly Sans Caps, Solbera
Imitation) as `data:font/opentype;base64,…` URIs inside `@font-face`
blocks, so no separate font files are vendored.

## Why we ship a scoped derivative

**The upstream file is not scoped to `.phb` despite the name suggesting
otherwise.** The first ~600 bytes are an Eric Meyer reset hitting bare
element selectors (`html, body, div, h1-h6, p, a, em, …`), and dozens of
later rules also target bare elements. Linking it globally would zero out
borders, padding, and font sizing across the whole app — Material icons
disappear, skill-card typography flattens, etc.

The homebrewery web app gets away with the file because it embeds the
stylesheet inside a `<body class="phb">` host page; the global rules then
only ever apply inside that wrapper by accident of context.

donjondocs is a standalone NiceGUI app. We need real scoping. The
`scope_phb_css.py` script in this directory rewrites every selector to
sit under a `.phb` ancestor and produces `phb.scoped.css`. That's the file
we actually serve via `<link>`. The standalone is kept in-tree as the
source of truth so we can re-run the scoper when upstream updates.

## How donjondocs uses it

`/_static/vendor/homebrewery/phb.scoped.css` is mounted by
`main.py::app.add_static_files(...)` and linked from
`app/ui/theme.py::apply_global_styles()`. The character-sheet "PHB style"
toggle (top bar) flips a `.phb` class on the `ui.markdown` elements inside
the Allies and Notes tabs (`app/ui/components/sheet/allies.py`,
`notes.py`). The toggle's value lives in `app.storage.user["phb_style"]`.
A small donjondocs-specific override in `theme.py` relaxes the printed-
page geometry (`width: 215.9mm; height: 279.4mm; column-count: 2`) so
markdown flows naturally inside our cards rather than overflowing into
off-screen "page two" columns.

## Updating the file

```sh
# 1. Fetch fresh upstream CSS
curl -sSL -o app/static/vendor/homebrewery/phb.standalone.css \
  https://raw.githubusercontent.com/naturalcrit/homebrewery/master/phb.standalone.css

# 2. Regenerate the scoped derivative
python app/static/vendor/homebrewery/scope_phb_css.py

# 3. Diff-review both files, then commit them together.
```

After updating, bump the **Fetched at commit** line above so future
maintainers can diff against the same baseline. If the scoper logs
`unknown at-rule` warnings, eyeball those rules in `phb.scoped.css` —
they're emitted verbatim and may need explicit handling in the script.

## License notes

The CSS is MIT-licensed. The fonts embedded inside the CSS originate from
several sources — Bookinsanity and Solbera Imitation are explicitly free
for D&D community use, while Mr Eaves Small Caps is upstream-of-debated
provenance. donjondocs ships the CSS verbatim, accepting whatever
redistribution choice the upstream homebrewery project has made; if your
deployment environment is sensitive to commercial-font redistribution,
consider stripping the affected `@font-face` blocks before shipping.
