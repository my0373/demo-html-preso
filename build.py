#!/usr/bin/env python3
"""Assemble index.html from src/.

    python3 build.py

src/template.html   the HTML slides engine (CSS tokens, navigation, diagram edges), unchanged
src/extra.css       deck additions (hero image, code blocks, jump search)
src/extra.js        deck additions (jump search, goto links, slide ids)
src/slides-*.html   the slides, in filename order, with {{PLACEHOLDERS}} filled in below

Bump the three version constants when the upstream release changes. The tag form is
vX.Y.Z-a.b.c, where X.Y.Z is NetBox and a.b.c is netbox-docker (see the netbox-docker README).
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"

NB = "4.7.2"          # NetBox core release
ND = "5.1.1"          # netbox-docker release
TAG = f"v{NB}-{ND}"   # container image tag
DOCS = "https://netboxlabs.com/docs/netbox/"

FOOTER = (
    '<div class="footer"><div class="brand"><div class="wordmark">netbox</div></div>'
    '<div class="right"><span>Community NetBox {{NB}} &middot; netbox-docker {{ND}}</span>'
    '<div class="num"></div></div></div>'
)


def must_replace(text, old, new, count=1):
    assert old in text, f"template no longer contains: {old[:70]!r}"
    return text.replace(old, new, count)


t = (SRC / "template.html").read_text()

t = re.sub(r"<title>.*?</title>", f"<title>Using Community NetBox {NB}</title>", t, count=1)
t = must_replace(t, "</style>", (SRC / "extra.css").read_text() + "</style>")

# slides replace the template's example sections
start = t.index('<nav class="topics" id="topics"></nav>') + len('<nav class="topics" id="topics"></nav>')
end = t.index('</div>\n</div>\n<div class="hint"')
slides = "\n".join(p.read_text() for p in sorted(SRC.glob("slides-*.html")))


def one_per_step(slides_html):
    """Give every data-in element its own step, in document order, per slide.
    Authors can then write data-in="1" anywhere and never get two items appearing together."""
    def per_slide(m):
        n = 0
        def bump(_):
            nonlocal n
            n += 1
            return f'data-in="{n}"'
        return re.sub(r'data-in="\d+"', bump, m.group(0))
    return re.sub(r"<section\b.*?</section>", per_slide, slides_html, flags=re.S)


slides = one_per_step(slides)
t = t[:start] + (
    '\n<button class="jumpbtn" id="jumpbtn" type="button">Jump to slide <kbd>G</kbd></button>\n'
    + slides + "\n"
) + t[end:]

t = must_replace(
    t,
    '<div class="ov" id="ov"><h2>Slides</h2><div class="ovg" id="ovg"></div></div>',
    '<div class="ov" id="ov"><div class="ovbar"><h2>Jump to a slide</h2>'
    '<input id="ovq" type="text" placeholder="Search titles or type a slide number" autocomplete="off" spellcheck="false">'
    '<span id="ovinfo"></span></div><div class="ovg" id="ovg"></div></div>',
)
t = must_replace(
    t,
    "&larr; &rarr; or space to navigate &middot; O overview &middot; F fullscreen",
    "&larr; &rarr; or space to navigate &middot; G or O jump to any slide &middot; F fullscreen",
)
t = must_replace(
    t,
    "  const h = parseInt(location.hash.slice(1), 10);\n  go(isNaN(h) ? 0 : h - 1);",
    (SRC / "extra.js").read_text()
    + "\n  const hs = location.hash.slice(1), hi = isNaN(+hs) ? slides.findIndex(s => s.id === hs) : +hs - 1;\n"
    "  go(hi < 0 || isNaN(hi) ? 0 : hi);",
)

t = t.replace("{{FOOTER}}", FOOTER)
for k, v in {"NB": NB, "ND": ND, "TAG": TAG, "D": DOCS}.items():
    t = t.replace("{{" + k + "}}", v)

left = re.findall(r"\{\{[A-Z]+\}\}", t)
assert not left, f"unfilled placeholders: {set(left)}"

(ROOT / "index.html").write_text(t)
print(f"index.html written: {len(t) // 1024} KB, {t.count('<section class=\"slide')} slides")
