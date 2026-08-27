#!/usr/bin/env python3
"""Post-render sitemap corrections.

Quarto enumerates only the documents it renders, and lists them by file name.
Two fixes:
  1. rewrite index.html to the bare directory URL, which is what the site is
     actually linked and served as;
  2. add music-calendar.html, a hand-maintained static page Quarto never sees
     (it is copied as a site resource, so it is never a rendered input).

Deliberately NOT done: removing publications.html. It canonicals to
research.html (see scripts/gen_publications.py) but nothing on the site links
to it, so the sitemap is Googlebot's only path to the page. Drop it and the
canonical may never be re-read, which defeats the consolidation entirely.

No lastmod is emitted for music-calendar.html: it is optional in the sitemaps
protocol, and every available timestamp is wrong under CI (actions/checkout
resets mtimes to checkout time, and the shallow clone makes git log unreliable).

Wired in as a project post-render step in _quarto.yml. Idempotent.
"""
import pathlib
import sys

SITEMAP = pathlib.Path("_site/sitemap.xml")
if not SITEMAP.exists():
    print("sitemap.xml not present; skipping", file=sys.stderr)
    sys.exit(0)

xml = SITEMAP.read_text(encoding="utf-8")

xml = xml.replace(
    "<loc>https://arthurberg.com/index.html</loc>",
    "<loc>https://arthurberg.com/</loc>",
)

if "music-calendar.html" not in xml:
    xml = xml.replace(
        "</urlset>",
        "  <url>\n"
        "    <loc>https://arthurberg.com/music-calendar.html</loc>\n"
        "  </url>\n</urlset>",
    )

SITEMAP.write_text(xml, encoding="utf-8")
print("Patched _site/sitemap.xml")
