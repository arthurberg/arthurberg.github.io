#!/usr/bin/env python3
"""Generate publications.qmd from a BibTeX file.

Groups entries by year (descending). Within each year, journal articles come
first, then proceedings, then other. Primary-authored papers (keyword=primary)
are marked with a star.

Usage: python3 scripts/gen_publications.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tag_publications import tag_entry, AREA_TAGS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "publications.bib"
OUT = ROOT / "publications.qmd"
OUT_BODY = ROOT / "_publications-body.qmd"
PDF_DIR = ROOT / "papers"  # local PDFs named <bibkey>.pdf (colons replaced with underscores)

# bibkey -> path for supplementary material pages
SUPPLEMENTS = {
    "Berg:2025aa": "news/2025-entropy-chinese.html",
}

TYPE_ORDER = {"article": 0, "inproceedings": 1, "misc": 2}
TYPE_LABEL = {
    "article": "Journal Articles",
    "inproceedings": "Conference Proceedings",
    "misc": "Other",
}


def clean(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\\&", "&").replace("--", "–")
    return s.strip()


def format_authors(raw: str) -> str:
    if not raw:
        return ""
    authors = [a.strip() for a in raw.split(" and ")]
    formatted = []
    for a in authors:
        if "," in a:
            last, first = a.split(",", 1)
            initials = "".join(
                p[0] + "." for p in first.strip().split() if p and p[0].isalpha()
            )
            formatted.append(f"{initials} {last.strip()}" if initials else last.strip())
        else:
            parts = a.strip().split()
            if len(parts) > 1:
                last = parts[-1]
                initials = "".join(p[0] + "." for p in parts[:-1] if p and p[0].isalpha())
                formatted.append(f"{initials} {last}")
            else:
                formatted.append(a)
    formatted = [clean(x) for x in formatted]
    bolded = [
        f'<span class="pub-me">{x}</span>' if "Berg" in x else x for x in formatted
    ]
    if len(bolded) <= 8:
        return ", ".join(bolded)
    return ", ".join(bolded[:8]) + ", et al."


def pdf_filename(bibkey: str) -> str:
    return bibkey.replace(":", "_") + ".pdf"


def render_entry(entry: dict) -> str:
    bibkey = entry.get("ID", "")
    authors = format_authors(entry.get("author", ""))
    title = clean(entry.get("title", ""))
    year = entry.get("year", "").strip()
    venue = entry.get("journal") or entry.get("booktitle") or entry.get("publisher") or ""
    venue = clean(venue)
    volume = clean(entry.get("volume", ""))
    number = clean(entry.get("number", ""))
    pages = clean(entry.get("pages", ""))
    doi = entry.get("doi", "").strip()
    url = entry.get("url", "").strip()

    vp = ""
    if venue:
        vp = f"*{venue}*"
        if volume:
            vp += f", {volume}"
            if number:
                vp += f"({number})"
        if pages:
            vp += f", {pages}"
        vp += "."

    links: list[str] = []
    pdf_rel = pdf_filename(bibkey)
    if (PDF_DIR / pdf_rel).exists():
        links.append(f'<a class="pub-badge pub-pdf" href="papers/{pdf_rel}">PDF</a>')
    if doi:
        links.append(
            f'<a class="pub-badge pub-doi" href="https://doi.org/{doi}">DOI</a>'
        )
    elif url and (url.startswith("http://") or url.startswith("https://")):
        links.append(f'<a class="pub-badge pub-link" href="{url}">Link</a>')
    if bibkey in SUPPLEMENTS:
        links.append(
            f'<a class="pub-badge pub-supp" href="{SUPPLEMENTS[bibkey]}">Supplement</a>'
        )
    link_str = (" " + " ".join(links)) if links else ""

    areas = tag_entry(entry)
    data_areas = " ".join(areas)

    title_html = f'<span class="pub-title">{title}.</span>'
    venue_html = f' <span class="pub-venue">{vp}</span>' if vp else ""
    meta_html = f'<div class="pub-meta">{authors} ({year}).</div>'
    body_html = f'<div class="pub-body">{title_html}{venue_html}{link_str}</div>'
    return f'<div class="pub-entry" data-areas="{data_areas}">{meta_html}{body_html}</div>'


def main() -> int:
    if not BIB.exists():
        print(f"Bib file not found: {BIB}", file=sys.stderr)
        return 1

    with BIB.open() as fh:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.load(fh, parser=parser)

    entries = [e for e in db.entries if e.get("year")]
    # Sort key: year descending, then type order, then title
    entries.sort(
        key=lambda e: (
            -int(re.sub(r"\D", "", e["year"]) or 0),
            TYPE_ORDER.get(e.get("ENTRYTYPE", "").lower(), 99),
            clean(e.get("title", "")).lower(),
        )
    )

    total = len(entries)
    years = sorted({re.sub(r"\D", "", e["year"]) for e in entries if e.get("year")})
    year_range = f"{years[0]}–{years[-1]}" if years else ""
    n_article = sum(1 for e in entries if e.get("ENTRYTYPE", "").lower() == "article")
    n_proc = sum(
        1 for e in entries if e.get("ENTRYTYPE", "").lower() == "inproceedings"
    )
    n_pdf = sum(
        1
        for e in entries
        if (PDF_DIR / pdf_filename(e.get("ID", ""))).exists()
    )

    # ——— Build body (stats + filter bar + entries) ———
    body: list[str] = []

    # Area tag labels for the filter chip bar
    area_labels = [
        ("all", "All"),
        ("methodology", "Methodology"),
        ("bayesian", "Bayesian"),
        ("clinical-trials-methods", "Clinical Trials"),
        ("statistical-genetics", "Statistical Genetics"),
        ("statistics-education", "Statistics Education"),
        ("nonparametric-methods", "Nonparametric"),
        ("information-theory", "Information Theory"),
        ("pediatric-oncology", "Pediatric Oncology"),
        ("adult-oncology", "Adult Oncology"),
        ("spinal-cord-injury", "Spinal Cord Injury"),
        ("neuroscience", "Neuroscience"),
        ("clinical-research", "Clinical Research"),
    ]

    body.append('::: {.pub-summary}')
    body.append('::: {.pub-stats}')
    body.append(f'<div class="pub-stat"><span class="pub-stat-num">{total}</span><span class="pub-stat-label">total</span></div>')
    body.append(f'<div class="pub-stat"><span class="pub-stat-num">{n_article}</span><span class="pub-stat-label">journal</span></div>')
    body.append(f'<div class="pub-stat"><span class="pub-stat-num">{n_proc}</span><span class="pub-stat-label">proceedings</span></div>')
    body.append(f'<div class="pub-stat"><span class="pub-stat-num">{n_pdf}</span><span class="pub-stat-label">with PDFs</span></div>')
    body.append(f'<div class="pub-stat"><span class="pub-stat-num">{year_range}</span><span class="pub-stat-label">years</span></div>')
    body.append(':::')
    body.append(':::')
    body.append("")

    # Filter chip bar
    body.append('<div class="pub-filter" role="toolbar" aria-label="Filter publications by research area">')
    for slug, label in area_labels:
        cls = "pub-filter-chip" + (" active" if slug == "all" else "")
        body.append(f'<button type="button" class="{cls}" data-filter="{slug}">{label}</button>')
    body.append('<span class="pub-filter-count" id="pub-filter-count"></span>')
    body.append('</div>')
    body.append("")

    current_year = None
    current_type = None
    for e in entries:
        y = re.sub(r"\D", "", e["year"]) or "Unknown"
        t = e.get("ENTRYTYPE", "").lower()
        if y != current_year:
            body.append("")
            body.append(f'<h2 class="pub-year" data-year="{y}">{y}</h2>')
            body.append("")
            current_year = y
            current_type = None
        if t != current_type:
            label = TYPE_LABEL.get(t, t.title())
            body.append(f'<h3 class="pub-type">{label}</h3>')
            body.append("")
            current_type = t
        body.append(render_entry(e))

    # Body fragment (no YAML, used by include shortcode elsewhere)
    body_text = "\n".join(body) + "\n"
    OUT_BODY.write_text(body_text)

    # Full standalone publications page
    page: list[str] = []
    page.append("---")
    page.append('title: "Publications"')
    page.append("toc: true")
    page.append("toc-depth: 2")
    page.append("---")
    page.append("")
    page.append('[**Download full CV (PDF)**](Berg-CV.pdf){.btn .btn-primary}')
    page.append('[ORCID](https://orcid.org/0000-0002-4097-7348){.btn .btn-outline-secondary}')
    page.append('[Penn State Pure](https://pennstate.pure.elsevier.com/en/persons/arthur-berg){.btn .btn-outline-secondary}')
    page.append('[Google Scholar](https://scholar.google.com/citations?user=asQf9VQAAAAJ){.btn .btn-outline-secondary}')
    page.append('')
    page.append(body_text)

    OUT.write_text("\n".join(page))
    print(f"Wrote {OUT} and {OUT_BODY} — {total} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
