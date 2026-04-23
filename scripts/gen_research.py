#!/usr/bin/env python3
"""Generate the unified Research-page body fragment.

Reads:
    publications.bib   — journal / proceedings entries
    data/grants.yml    — extramural support (parsed from myResearch portal)
    data/protocols.yml — IRB/IACUC/IBC protocols

Produces:
    _research-body.qmd       — filterable body fragment (publications + grants + protocols)
    publications.qmd         — standalone filterable publications page (legacy URL)
    _publications-body.qmd   — body-only fragment (for any direct include)

Research-area tagging reuses scripts/tag_publications.py:tag_entry for
publications and a simplified rule set for grants / protocols.

Usage:  python3 scripts/gen_research.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import bibtexparser
import yaml
from bibtexparser.bparser import BibTexParser

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from tag_publications import tag_entry  # noqa: E402

ROOT = SCRIPTS.parent
BIB = ROOT / "publications.bib"
GRANTS_YML = ROOT / "data" / "grants.yml"
PROTOCOLS_YML = ROOT / "data" / "protocols.yml"

OUT_BODY = ROOT / "_research-body.qmd"
OUT_PUB = ROOT / "publications.qmd"
OUT_PUB_BODY = ROOT / "_publications-body.qmd"
PDF_DIR = ROOT / "papers"

SUPPLEMENTS = {
    "Berg:2025aa": "news/2025-entropy-chinese.html",
}

TYPE_ORDER = {"article": 0, "inproceedings": 1, "misc": 2}
TYPE_LABEL = {
    "article": "Journal Articles",
    "inproceedings": "Conference Proceedings",
    "misc": "Other",
}

AREA_LABELS = [
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

AREA_LABEL_LOOKUP = {slug: label for slug, label in AREA_LABELS if slug != "all"}


def area_tags_html(areas: list[str]) -> str:
    if not areas:
        return ""
    pills = []
    for a in areas:
        label = AREA_LABEL_LOOKUP.get(a, a)
        pills.append(f'<span class="area-tag" data-area="{a}">{label}</span>')
    return '<div class="area-tags">' + "".join(pills) + '</div>'

TYPE_FILTERS = [
    ("all", "Everything"),
    ("publication", "Publications"),
    ("abstract", "Abstracts"),
    ("grant", "Grants"),
    ("protocol", "Protocols"),
]


# ——— Shared helpers ———

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


# ——— Publications rendering ———

_ANNOTE_CLEAN_RX = [
    (re.compile(r"\\emph\{([^{}]*)\}"), r"<em>\1</em>"),
    (re.compile(r"\\textit\{([^{}]*)\}"), r"<em>\1</em>"),
    (re.compile(r"\\textbf\{([^{}]*)\}"), r"<strong>\1</strong>"),
    (re.compile(r"\\url\{([^{}]*)\}"), r'<a href="\1">\1</a>'),
    (re.compile(r"\\MYhref\{([^{}]*)\}\{[^{}]*\}"), r'<a href="\1">\1</a>'),
    (re.compile(r"\\href\{([^{}]*)\}\{([^{}]*)\}"), r'<a href="\1">\2</a>'),
    (re.compile(r"\\nolinkurl\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\&"), "&amp;"),
]


def format_annote(raw: str) -> str:
    if not raw:
        return ""
    text = raw.replace("\n", " ")
    for pat, repl in _ANNOTE_CLEAN_RX:
        text = pat.sub(repl, text)
    # drop any stray { } left behind from nested latex
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def render_pub(entry: dict) -> str:
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
    annote = format_annote(entry.get("annote", "") or entry.get("annotation", ""))

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
        links.append(f'<a class="pub-badge pub-doi" href="https://doi.org/{doi}">DOI</a>')
    elif url and (url.startswith("http://") or url.startswith("https://")):
        links.append(f'<a class="pub-badge pub-link" href="{url}">Link</a>')
    if bibkey in SUPPLEMENTS:
        links.append(f'<a class="pub-badge pub-supp" href="{SUPPLEMENTS[bibkey]}">Supplement</a>')
    link_str = (" " + " ".join(links)) if links else ""

    areas = tag_entry(entry)
    data_areas = " ".join(areas)
    data_type = "abstract" if entry.get("keywords") == "conference" else "publication"

    title_html = f'<span class="pub-title">{title}.</span>'
    venue_html = f' <span class="pub-venue">{vp}</span>' if vp else ""
    meta_html = f'<div class="pub-meta">{authors} ({year}).</div>'
    tags_html = area_tags_html(areas)
    annote_html = f'<div class="pub-annote">{annote}</div>' if annote else ""
    body_html = f'<div class="pub-body">{title_html}{venue_html}{link_str}{tags_html}{annote_html}</div>'
    return (
        f'<div class="pub-entry" data-type="{data_type}" data-areas="{data_areas}">'
        f'{meta_html}{body_html}</div>'
    )


# ——— Grants tagging + rendering ———

GRANT_TAG_RULES = [
    (r"bayesian", "bayesian"),
    (r"neuroblastoma|pediatric|childhood|acute myeloid leukemia|osteosarcoma|ewing sarcoma|dipg|medulloblastoma", "pediatric-oncology"),
    (r"melanoma|pancreatic|breast cancer|colorectal|cancer|tumor|chemotherap|aldehyde dehydrogenase|glioblastoma|bile|biliary|cholangio|oncology|immunotherap|lung cancer|carcinoma|persister", "adult-oncology"),
    (r"spinal cord|\bsci\b|paraplegi|science", "spinal-cord-injury"),
    (r"alzheimer|olfact|memory|neurodegen|brain|parkinson|dbs", "neuroscience"),
    (r"gwas|genom|heritabil|methylation|gene expression|pre-mrna|splicing", "statistical-genetics"),
    (r"primary care|family medicine|burnout|medical student|training|education", "statistics-education|clinical-research"),  # ambiguous
    (r"trial design|clinical trial|phase\s*(i|ii|iii|0|iv)", "clinical-trials-methods"),
    (r"heat stress|obesity|nutrition|thermal", "clinical-research"),
    (r"regulatory t cell|arthritis", "clinical-research"),
]


def tag_grant(grant: dict) -> list[str]:
    title = (grant.get("title") or "").lower()
    sponsor = (grant.get("sponsor") or "").lower()
    pi = (grant.get("pi") or "").lower()
    haystack = f"{title} {sponsor} {pi}"
    tags: set[str] = set()

    for pattern, tag in GRANT_TAG_RULES:
        if re.search(pattern, haystack):
            # handle ambiguous multi-tag directives
            for t in tag.split("|"):
                tags.add(t)

    # BCC trials always pediatric-oncology + clinical-trials-methods
    if "bcc" in haystack or "naxitamab" in haystack or "dfmo" in haystack:
        tags.add("pediatric-oncology")
        tags.add("clinical-trials-methods")

    # Author-based disambiguation
    if "sholler" in pi:
        tags.add("pediatric-oncology")
    if "gater" in pi or "farkas" in pi:
        tags.add("spinal-cord-injury")
    if "sharma" in pi and "child" in haystack:
        tags.add("pediatric-oncology")

    # Training programs aren't "statistics-education" — push to clinical-research
    if "primary care training" in title or "area health education" in title:
        tags.discard("statistics-education")
        tags.add("clinical-research")

    if not tags:
        tags.add("clinical-research")
    return sorted(tags)


def grant_status_badge(status: str) -> str:
    return {
        "active":    '<span class="status-badge status-active">Active</span>',
        "pending":   '<span class="status-badge status-pending">Pending</span>',
        "completed": '<span class="status-badge status-completed">Completed</span>',
    }.get(status, "")


def render_grant(g: dict) -> str:
    tags = tag_grant(g)
    data_areas = " ".join(tags)
    badge = grant_status_badge(g.get("status", ""))
    pi = g.get("pi", "")
    sponsor = g.get("sponsor", "")
    role = g.get("role", "")
    period = g.get("period") or (
        f'{g.get("start_year","")}' if g.get("start_year") and not g.get("end_year")
        else f'{g.get("start_year","")}–{g.get("end_year","")}' if g.get("start_year") else ""
    )
    budget = g.get("budget", "")
    award_num = g.get("award_number", "")

    # Pending grants often contain confidential specific-aims language in the
    # submitted title. When a `topic` field is supplied for a pending grant we
    # display that general topic area instead of the submitted title.
    topic = (g.get("topic") or "").strip()
    if g.get("status") == "pending" and topic:
        title = f"Topic area — {topic}"
    else:
        title = g.get("title", "").strip()

    meta_parts = []
    if period:
        meta_parts.append(period)
    if pi:
        meta_parts.append(f"PI: {pi}")
    if sponsor:
        meta_parts.append(sponsor)
    meta = " · ".join(meta_parts)

    detail_parts = []
    if role:
        detail_parts.append(f"Role: {role}")
    if budget:
        detail_parts.append(f"Budget: {budget}")
    if award_num:
        detail_parts.append(f"# {award_num}")
    detail = " · ".join(detail_parts)

    tags_html = area_tags_html(tags)
    body = f'<div class="pub-body"><span class="pub-title">{title}.</span>'
    if detail:
        body += f' <span class="pub-venue">{detail}</span>'
    body += tags_html
    body += '</div>'

    return (
        f'<div class="pub-entry grant-entry" data-type="grant" data-areas="{data_areas}">'
        f'<div class="pub-meta">{badge} {meta}</div>{body}</div>'
    )


# ——— Protocols tagging + rendering ———

PROTOCOL_TAG_RULES = [
    (r"neuroblastoma|pediatric|childhood|ewing sarcoma|osteosarcoma|dfmo|eflornithine|bcc\d|medulloblastoma|dipg", "pediatric-oncology"),
    (r"pancreatic|colon|rectal|anal|cancer|tumor|vesicles|carcinoma|oncology", "adult-oncology"),
    (r"olfactory|memory|alzheimer|neurodegen|cns tumor|brain|neur", "neuroscience"),
    (r"veggie|vegetable|obesity|heat|nutrition|diabetes", "clinical-research"),
    (r"burnout|family medicine|medical student|opioid|primary care|women faculty|telephone|televideo|gait|runscribe|wearable|educational|autism", "clinical-research"),
    (r"barrett", "adult-oncology"),
    (r"genetic|biomarker|methylation|vesicle", "statistical-genetics"),
]


def tag_protocol(p: dict) -> list[str]:
    title = (p.get("title") or "").lower()
    sponsor = (p.get("sponsor") or "").lower()
    haystack = f"{title} {sponsor}"
    tags: set[str] = set()
    for pattern, tag in PROTOCOL_TAG_RULES:
        if re.search(pattern, haystack):
            tags.add(tag)
    if not tags:
        tags.add("clinical-research")
    return sorted(tags)


def render_protocol(p: dict) -> str:
    tags = tag_protocol(p)
    data_areas = " ".join(tags)
    badge = grant_status_badge(p.get("status", ""))
    sponsor = p.get("sponsor", "")
    role = p.get("role", "")
    approval = p.get("approval_date", "")
    expiration = p.get("expiration_date", "")
    pid = p.get("id", "")
    ptype = p.get("type", "")

    period_parts = []
    if approval:
        period_parts.append(f"Approved {approval}")
    if expiration:
        period_parts.append(f"Expires {expiration}")
    period = " · ".join(period_parts)

    meta_parts = []
    if period:
        meta_parts.append(period)
    if sponsor and sponsor.lower() != "none":
        meta_parts.append(sponsor)
    meta = " · ".join(meta_parts) if meta_parts else "Investigator-initiated"

    detail_parts = []
    if role:
        detail_parts.append(f"Role: {role}")
    if pid:
        detail_parts.append(f"# {pid}")
    if ptype:
        detail_parts.append(ptype)
    detail = " · ".join(detail_parts)

    title = p.get("title", "")
    tags_html = area_tags_html(tags)
    body = f'<div class="pub-body"><span class="pub-title">{title}.</span>'
    if detail:
        body += f' <span class="pub-venue">{detail}</span>'
    body += tags_html
    body += '</div>'

    return (
        f'<div class="pub-entry protocol-entry" data-type="protocol" data-areas="{data_areas}">'
        f'<div class="pub-meta">{badge} {meta}</div>{body}</div>'
    )


# ——— Build filter bar ———

def filter_bar_html() -> str:
    lines = []
    lines.append('<div class="pub-filter" role="toolbar" aria-label="Filter by type and research area">')

    lines.append('<div class="pub-filter-row pub-filter-types">')
    lines.append('<span class="pub-filter-label">Type:</span>')
    for slug, label in TYPE_FILTERS:
        cls = "pub-filter-chip pub-filter-type" + (" active" if slug == "all" else "")
        lines.append(f'<button type="button" class="{cls}" data-type-filter="{slug}">{label}</button>')
    lines.append('</div>')

    lines.append('<div class="pub-filter-row pub-filter-areas">')
    lines.append('<span class="pub-filter-label">Area:</span>')
    for slug, label in AREA_LABELS:
        cls = "pub-filter-chip" + (" active" if slug == "all" else "")
        lines.append(f'<button type="button" class="{cls}" data-filter="{slug}">{label}</button>')
    lines.append('<span class="pub-filter-count" id="pub-filter-count"></span>')
    lines.append('</div>')

    lines.append('</div>')
    return "\n".join(lines)


# ——— Load data ———

def load_publications() -> list[dict]:
    with BIB.open() as f:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.load(f, parser=parser)
    entries = [e for e in db.entries if e.get("year")]
    entries.sort(
        key=lambda e: (
            -int(re.sub(r"\D", "", e["year"]) or 0),
            TYPE_ORDER.get(e.get("ENTRYTYPE", "").lower(), 99),
            clean(e.get("title", "")).lower(),
        )
    )
    return entries


def load_grants() -> list[dict]:
    if not GRANTS_YML.exists():
        return []
    with GRANTS_YML.open() as f:
        return yaml.safe_load(f) or []


def load_protocols() -> list[dict]:
    if not PROTOCOLS_YML.exists():
        return []
    with PROTOCOLS_YML.open() as f:
        return yaml.safe_load(f) or []


# ——— Assemble output ———

def research_stats_block(entries: list[dict], grants: list[dict], protocols: list[dict]) -> str:
    n_abs = sum(1 for e in entries if e.get("keywords") == "conference")
    n_pub = len(entries) - n_abs
    return (
        '::: {.pub-summary}\n'
        '::: {.pub-stats}\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_pub}</span><span class="pub-stat-label">publications</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_abs}</span><span class="pub-stat-label">abstracts</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{len(grants)}</span><span class="pub-stat-label">grants</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{len(protocols)}</span><span class="pub-stat-label">protocols</span></div>\n'
        ':::\n:::\n'
    )


def pub_only_stats_block(entries: list[dict]) -> str:
    n_abs = sum(1 for e in entries if e.get("keywords") == "conference")
    n_pub = len(entries) - n_abs
    years = sorted({re.sub(r"\D", "", e["year"]) for e in entries if e.get("year")})
    year_range = f"{years[0]}–{years[-1]}" if years else ""
    n_pdf = sum(1 for e in entries if (PDF_DIR / pdf_filename(e.get("ID", ""))).exists())

    return (
        '::: {.pub-summary}\n'
        '::: {.pub-stats}\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_pub}</span><span class="pub-stat-label">publications</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_abs}</span><span class="pub-stat-label">abstracts</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_pdf}</span><span class="pub-stat-label">with PDFs</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{year_range}</span><span class="pub-stat-label">years</span></div>\n'
        ':::\n:::\n'
    )


def _build_entries_section(entries: list[dict], section_id: str, data_section: str,
                           heading: str, show_type_subheads: bool = True) -> list[str]:
    out = [
        f'<section id="{section_id}" class="research-section" data-section="{data_section}">',
        f'<h2 class="section-heading">{heading}</h2>',
    ]
    current_year = None
    current_type = None
    for e in entries:
        y = re.sub(r"\D", "", e["year"]) or "Unknown"
        t = e.get("ENTRYTYPE", "").lower()
        if y != current_year:
            out.append(f'<h3 class="pub-year" data-year="{y}">{y}</h3>')
            current_year = y
            current_type = None
        if show_type_subheads and t != current_type:
            label = TYPE_LABEL.get(t, t.title())
            out.append(f'<h4 class="pub-type">{label}</h4>')
            current_type = t
        out.append(render_pub(e))
    out.append('</section>')
    return out


def build_publications_section(entries: list[dict]) -> list[str]:
    pubs = [e for e in entries if e.get("keywords") != "conference"]
    abstracts = [e for e in entries if e.get("keywords") == "conference"]
    out: list[str] = []
    if pubs:
        out.extend(_build_entries_section(pubs, "sec-publications", "publication", "Publications",
                                          show_type_subheads=False))
    if abstracts:
        out.extend(_build_entries_section(abstracts, "sec-abstracts", "abstract",
                                          "Conference Abstracts",
                                          show_type_subheads=False))
    return out


def build_grants_section(grants: list[dict]) -> list[str]:
    out = [
        '<section id="sec-grants" class="research-section" data-section="grant">',
        '<h2 class="section-heading">Grants</h2>',
        '<p class="section-intro">Extramural research support — active, pending, and completed awards.</p>',
    ]
    for status_slug, status_label in [("active", "Active"), ("pending", "Pending"), ("completed", "Completed")]:
        bucket = [g for g in grants if g.get("status") == status_slug]
        if not bucket:
            continue
        out.append(f'<h3 class="grant-status-heading" data-status="{status_slug}">{status_label}</h3>')
        for g in bucket:
            out.append(render_grant(g))
    out.append('</section>')
    return out


def build_protocols_section(protocols: list[dict]) -> list[str]:
    out = [
        '<section id="sec-protocols" class="research-section" data-section="protocol">',
        '<h2 class="section-heading">Protocols</h2>',
        '<p class="section-intro">IRB/IACUC/IBC research protocols on which I serve as Principal Investigator, '
        'Co-Investigator, or Research Support.</p>',
    ]
    active = [p for p in protocols if p.get("status") != "pending"]
    pending = [p for p in protocols if p.get("status") == "pending"]
    if active:
        out.append('<h3 class="grant-status-heading" data-status="active">Active</h3>')
        # Sort by approval date desc
        active.sort(key=lambda p: (p.get("approval_date") or ""), reverse=True)
        for p in active:
            out.append(render_protocol(p))
    if pending:
        out.append('<h3 class="grant-status-heading" data-status="pending">Pending</h3>')
        for p in pending:
            out.append(render_protocol(p))
    out.append('</section>')
    return out


def main() -> int:
    if not BIB.exists():
        print(f"Missing: {BIB}", file=sys.stderr)
        return 1

    pubs = load_publications()
    grants = load_grants()
    protocols = load_protocols()

    # Unified research-body fragment
    parts: list[str] = []
    parts.append(research_stats_block(pubs, grants, protocols))
    parts.append('')
    parts.append(filter_bar_html())
    parts.append('')

    parts.extend(build_publications_section(pubs))
    if grants:
        parts.extend(build_grants_section(grants))
    if protocols:
        parts.extend(build_protocols_section(protocols))

    body_text = "\n".join(parts) + "\n"
    OUT_BODY.write_text(body_text)

    # Publications-only body fragment (legacy URL)
    pub_parts: list[str] = [pub_only_stats_block(pubs), ""]
    pub_parts.append(filter_bar_html())
    pub_parts.append("")
    pub_parts.extend(build_publications_section(pubs))
    OUT_PUB_BODY.write_text("\n".join(pub_parts) + "\n")

    # Standalone publications page (still reachable at /publications.html)
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
    page.append("")
    page.append("\n".join(pub_parts))
    OUT_PUB.write_text("\n".join(page))

    print(f"Wrote {OUT_BODY} — {len(pubs)} publications, {len(grants)} grants, {len(protocols)} protocols")
    print(f"Wrote {OUT_PUB} and {OUT_PUB_BODY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
