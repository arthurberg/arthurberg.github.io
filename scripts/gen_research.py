#!/usr/bin/env python3
"""Generate the unified Research-page body fragment.

Reads:
    publications.bib   — journal / proceedings entries
    data/grants.yml    — extramural support (parsed from myResearch portal)

Produces:
    _research-body.qmd       — filterable body fragment (publications + grants)

publications.qmd / _publications-body.qmd are owned by scripts/gen_publications.py.
Both scripts used to write them, with different markup, so whichever ran last
won — keep the ownership split.

Research-area tagging reuses scripts/tag_publications.py:tag_entry for
publications and a simplified rule set for grants.

Protocols were dropped from the rendered Research page in Apr 2026 (commit
ca207c5). PROTOCOLS_YML, tag_protocol/render_protocol, load_protocols, and
build_protocols_section are kept ON PURPOSE as dead code so the section can be
revived, and data/protocols.yml is kept in step with them. Reviving it needs
both a build_protocols_section() call in main() AND a ("protocol", "Protocols")
entry in TYPE_FILTERS.

Usage:  python3 scripts/gen_research.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import bibtexparser
import yaml
from bibtexparser.bparser import BibTexParser


def html_escape(s: str) -> str:
    """Escape for use inside a double-quoted HTML attribute."""
    return html.escape(s or "", quote=True)


def is_abstract(entry: dict) -> bool:
    """True for conference abstracts.

    Tests membership rather than equality: tag_publications.py appends area
    tags to `keywords`, so the field is often "conference, bayesian, ..." and
    an `== "conference"` test would quietly reclassify every abstract.
    """
    return "conference" in {t.strip() for t in (entry.get("keywords") or "").split(",")}

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from tag_publications import tag_entry  # noqa: E402

ROOT = SCRIPTS.parent
BIB = ROOT / "publications.bib"
GRANTS_YML = ROOT / "data" / "grants.yml"
PROTOCOLS_YML = ROOT / "data" / "protocols.yml"

OUT_BODY = ROOT / "_research-body.qmd"
PDF_DIR = ROOT / "papers"

SUPPLEMENTS = {
    "Berg:2025aa": "news/2025-entropy-chinese.html",
}

TYPE_ORDER = {"article": 0, "inproceedings": 1, "misc": 2}

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
        # <button>, not <span>: these filter the page when clicked, so they
        # have to be reachable and operable from the keyboard.
        pills.append(
            f'<button type="button" class="area-tag" data-area="{a}" '
            f'aria-label="Filter by {label}">{label}</button>'
        )
    return '<div class="area-tags">' + "".join(pills) + '</div>'

TYPE_FILTERS = [
    ("all", "Everything"),
    ("publication", "Publications"),
    ("abstract", "Abstracts"),
    ("grant", "Grants"),
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
    berg_at = next((i for i, x in enumerate(formatted) if re.search(r"\bBerg\b", x)), None)
    bolded = [
        f'<span class="pub-me">{x}</span>' if re.search(r"\bBerg\b", x) else x for x in formatted
    ]
    if len(bolded) <= 8:
        return ", ".join(bolded)
    # On a long author list, keep Berg visible rather than truncating him away —
    # this is his publication list, and he is author 9+ on a number of papers.
    if berg_at is not None and berg_at >= 8:
        return ", ".join(bolded[:7]) + ", … " + bolded[berg_at] + ", et al."
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
    # LaTeX quoting is correct in the .bib (it is shared with the LaTeX CV) but
    # renders as literal backticks in HTML — translate to real quote marks.
    (re.compile(r"``(.+?)''"), r"“\1”"),
    (re.compile(r"`(.+?)'"), r"‘\1’"),
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

    # Hundreds of these badges share the text "PDF"/"DOI"; the title in the
    # aria-label is what tells a screen-reader user which paper they lead to.
    lbl = html_escape(title)
    links: list[str] = []
    pdf_rel = pdf_filename(bibkey)
    if (PDF_DIR / pdf_rel).exists():
        links.append(f'<a class="pub-badge pub-pdf" href="papers/{pdf_rel}" aria-label="PDF: {lbl}">PDF</a>')
    if doi:
        links.append(f'<a class="pub-badge pub-doi" href="https://doi.org/{doi}" aria-label="DOI: {lbl}">DOI</a>')
    elif url and (url.startswith("http://") or url.startswith("https://")):
        links.append(f'<a class="pub-badge pub-link" href="{url}" aria-label="Link: {lbl}">Link</a>')
    if bibkey in SUPPLEMENTS:
        links.append(
            f'<a class="pub-badge pub-supp" href="{SUPPLEMENTS[bibkey]}" '
            f'aria-label="Supplement: {lbl}">Supplement</a>'
        )
    link_str = (" " + " ".join(links)) if links else ""

    areas = tag_entry(entry)
    data_areas = " ".join(areas)
    data_type = "abstract" if is_abstract(entry) else "publication"

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

# Oncology context required before the generic age words below count as
# *pediatric oncology* — otherwise any pediatric study lands under it.
GRANT_ONC = (r"cancer|oncolog|leukemi|lymphoma|sarcoma|tumor|glioma|carcinoma|"
             r"malignan|chemotherap|neoplas|metasta|neuroblastoma|medulloblastoma")

GRANT_TAG_RULES = [
    (r"bayesian", "bayesian"),
    (r"neuroblastoma|acute myeloid leukemia|osteosarcoma|ewing sarcoma|dipg|medulloblastoma", "pediatric-oncology"),
    (rf"(?=.*(?:pediatric|paediatric|childhood))(?=.*(?:{GRANT_ONC}))", "pediatric-oncology"),
    (r"melanoma|pancreatic|breast cancer|colorectal|cancer|tumor|chemotherap|aldehyde dehydrogenase|glioblastoma|bile|biliary|cholangio|oncology|immunotherap|lung cancer|carcinoma|persister", "adult-oncology"),
    (r"spinal cord|\bsci\b|paraplegi", "spinal-cord-injury"),
    (r"alzheimer|olfact|memory|neurodegen|brain|parkinson|dbs", "neuroscience"),
    (r"gwas|genom|heritabil|methylation|gene expression|pre-mrna|splicing", "statistical-genetics"),
    (r"primary care|family medicine|burnout|medical student|training|education", "statistics-education|clinical-research"),  # ambiguous
    (r"trial design|clinical trial|phase\s*(i|ii|iii|0|iv)", "clinical-trials-methods"),
    (r"heat stress|obesity|nutrition|thermal", "clinical-research"),
    (r"regulatory t cell|arthritis", "clinical-research"),
]


def tag_grant(grant: dict) -> list[str]:
    # Pending grants carry a sanitized `topic` in place of the confidential
    # submitted title — match on whichever describes the science.
    subject = f'{grant.get("title") or ""} {grant.get("topic") or ""}'.lower().strip()
    pi = (grant.get("pi") or "").lower()
    # Deliberately excludes the sponsor: funder names ("Cannonball Kids' Cancer
    # Foundation", "Melanoma Research Foundation") describe who pays, not what
    # the work is about, and leak wrong area tags when matched.
    haystack = subject
    tags: set[str] = set()

    def apply_rules(text: str) -> set[str]:
        found: set[str] = set()
        for pattern, tag in GRANT_TAG_RULES:
            if re.search(pattern, text):
                # handle ambiguous multi-tag directives
                found.update(tag.split("|"))
        return found

    tags |= apply_rules(haystack)
    # Only when the subject says nothing usable does the sponsor get a vote —
    # it is the weakest signal, but better than the clinical-research catchall.
    if not tags:
        tags |= apply_rules((grant.get("sponsor") or "").lower())

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

    # "Training"/"education" in a disease-area grant means clinical training,
    # not statistics pedagogy — statistics-education is for actual stats teaching.
    if "statistics-education" in tags and (
        tags & {"pediatric-oncology", "adult-oncology", "spinal-cord-injury", "neuroscience"}
        or "primary care training" in subject
        or "area health education" in subject
    ):
        tags.discard("statistics-education")
        tags.add("clinical-research")

    # A pediatric study is not also adult oncology (mirrors tag_entry's rule)
    if "pediatric-oncology" in tags:
        tags.discard("adult-oncology")

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
    lines.append('<div class="pub-filter" role="group" aria-label="Filter by type and research area">')

    lines.append('<div class="pub-filter-row pub-filter-types" role="group" aria-label="Type">')
    lines.append('<span class="pub-filter-label">Type:</span>')
    for slug, label in TYPE_FILTERS:
        cls = "pub-filter-chip pub-filter-type" + (" active" if slug == "all" else "")
        lines.append(f'<button type="button" class="{cls}" data-type-filter="{slug}">{label}</button>')
    lines.append('</div>')

    lines.append('<div class="pub-filter-row pub-filter-areas" role="group" aria-label="Research area">')
    lines.append('<span class="pub-filter-label">Area:</span>')
    for slug, label in AREA_LABELS:
        cls = "pub-filter-chip" + (" active" if slug == "all" else "")
        lines.append(f'<button type="button" class="{cls}" data-filter="{slug}">{label}</button>')
    lines.append('</div>')

    # Result count sits on its own row, not inside the "Research area" group:
    # it is a status message about the whole filter, and .pub-filter is a
    # column flexbox, so this also stops it trailing the last area chip.
    lines.append('<span class="pub-filter-count" id="pub-filter-count"></span>')

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

def research_stats_block(entries: list[dict], grants: list[dict]) -> str:
    n_abs = sum(1 for e in entries if is_abstract(e))
    n_pub = len(entries) - n_abs
    # Count only grants that actually render (bucketed by status below);
    # anything with an unknown status would otherwise inflate the stat.
    n_grants = sum(1 for g in grants if g.get("status") in ("active", "pending", "completed"))
    return (
        '::: {.pub-summary}\n'
        '::: {.pub-stats}\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_pub}</span><span class="pub-stat-label">publications</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_abs}</span><span class="pub-stat-label">abstracts</span></div>\n'
        f'<div class="pub-stat"><span class="pub-stat-num">{n_grants}</span><span class="pub-stat-label">grants</span></div>\n'
        ':::\n:::\n'
    )


def _build_entries_section(entries: list[dict], section_id: str, data_section: str,
                           heading: str) -> list[str]:
    out = [
        f'<section id="{section_id}" class="research-section" data-section="{data_section}">',
        f'<h2 class="section-heading">{heading}</h2>',
    ]
    current_year = None
    for e in entries:
        y = re.sub(r"\D", "", e["year"]) or "Unknown"
        if y != current_year:
            out.append(f'<h3 class="pub-year" data-year="{y}">{y}</h3>')
            current_year = y
        out.append(render_pub(e))
    out.append('</section>')
    return out


def build_publications_section(entries: list[dict]) -> list[str]:
    pubs = [e for e in entries if not is_abstract(e)]
    abstracts = [e for e in entries if is_abstract(e)]
    out: list[str] = []
    if pubs:
        out.extend(_build_entries_section(pubs, "sec-publications", "publication", "Publications"))
    if abstracts:
        out.extend(_build_entries_section(abstracts, "sec-abstracts", "abstract",
                                          "Conference Abstracts"))
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

    # Unified research-body fragment
    parts: list[str] = []
    parts.append(research_stats_block(pubs, grants))
    parts.append('')
    parts.append(filter_bar_html())
    parts.append('')

    parts.extend(build_publications_section(pubs))
    if grants:
        parts.extend(build_grants_section(grants))

    body_text = "\n".join(parts) + "\n"
    OUT_BODY.write_text(body_text)

    print(f"Wrote {OUT_BODY} — {len(pubs)} publications, {len(grants)} grants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
