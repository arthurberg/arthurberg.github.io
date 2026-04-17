#!/usr/bin/env python3
"""Auto-tag publications.bib entries with research-area keywords.

Reads publications.bib, applies pattern-matching rules against title,
venue (journal/booktitle), and author list to add research-area slugs
to the `keywords` field of each entry (preserving existing authorship
tags like `primary`, `secondary`, `abstract`).

Usage:
    python3 scripts/tag_publications.py          # dry-run, show distribution
    python3 scripts/tag_publications.py --write  # write back to publications.bib
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "publications.bib"

# Existing authorship/status tags that should not be clobbered
STATUS_TAGS = {"primary", "secondary", "abstract", "submitted",
               "correction", "revision", "arxiv"}

# Area tags vocabulary
AREA_TAGS = [
    "methodology", "bayesian", "clinical-trials-methods",
    "statistical-genetics", "statistics-education",
    "nonparametric-methods", "information-theory",
    "pediatric-oncology", "adult-oncology", "spinal-cord-injury",
    "neuroscience", "clinical-research",
]

METHOD_VENUES = {
    "the american statistician", "teaching statistics", "biometrics",
    "test", "chance", "the mathematical intelligencer",
    "journal of the american statistical association",
    "journal of multivariate analysis", "statistics in medicine",
    "colombian journal of statistics", "statistical applications in genetics and molecular biology",
    "genetics", "clinical and translational science",
    "journal of statistical planning and inference",
}

SPINAL_AUTHORS = {"farkas", "gater", "dolbow", "gorgey", "sneij"}
PEDI_AUTHORS = {"sholler", "kraveka", "huang", "mitchell", "brown", "loeb", "offenbacher"}
GENETICS_AUTHORS = {"mcguire", "wu", "carrel", "rongling"}
FAMILY_MED_AUTHORS = {"oser", "parascando", "riley", "leong", "onks", "loeffert", "silvis"}
SURGERY_AUTHORS = {"koltun", "yochum", "kline", "schieffer", "deutsch", "jeganathan",
                   "scow", "mankarious", "hughes"}


def norm(s: str) -> str:
    return (s or "").lower().replace("{", "").replace("}", "")


def tag_entry(entry: dict) -> list[str]:
    """Return list of area tags for a single entry."""
    title = norm(entry.get("title", ""))
    journal = norm(entry.get("journal", "") or entry.get("booktitle", "") or entry.get("publisher", ""))
    authors = norm(entry.get("author", ""))

    tags: set[str] = set()

    # ——— Methodological ———
    is_method = False

    if re.search(r"\bbayes(ian)?\b|\bprior\b|posterior|rope|empirical bayes|bayes factor|shrinkage", title):
        tags.add("bayesian")
        is_method = True

    if re.search(r"noninferior|sample size|clinical trial|ctsa|clinicaltrials|trial design|adaptive design|dose escalat|stopping rule|interim analys|randomi[sz]ation", title):
        tags.add("clinical-trials-methods")
        is_method = True

    if re.search(r"causal inference|high-dimensional|\blag window|effect-measure modification|risk difference|odds ratio", title):
        is_method = True

    if re.search(r"genome|gwas|heritability|polygenic|snp\b|rs\d{4,}|allele|genetic variant|methylation|epigenet|transcriptom|sequencing|expression|microarray|linkage|qtl\b|pleiotropic|functional mapping|colq|arhgap|slc30a8|znt8|mbl2|il10|\bgene\b|microbiota", title):
        tags.add("statistical-genetics")

    if re.search(r"teaching|classroom|student|taxicab|basketball|imdb|olympiad|pedagog|introductory|aime|monte carlo simulation", title) or "teaching statistics" in journal or journal == "the mathematical intelligencer" or journal == "chance":
        tags.add("statistics-education")
        is_method = True

    if re.search(r"\btime series\b|bispectr|spectrum|spectra|bootstrap|bandwidth|lag[- ]window|density estimation|hazard estimation|kaplan[- ]meier|reduced bias|nonparametric|flat-top|s-th order|jensen|jensen's inequality|resampling", title):
        tags.add("nonparametric-methods")
        is_method = True

    if re.search(r"\bentropy\b|information[- ]theoretic|mutual information|sound[- ]character|chinese character|language learning|pinyin", title):
        tags.add("information-theory")
        is_method = True

    # ——— Applied areas ———
    # Pediatric oncology: BCC trials, childhood cancer, DIPG, pediatric leukemia
    if re.search(r"pediatric|childhood|children|paediatric|neuroblastoma|medulloblastoma|\bdipg\b|ewing sarcoma|pediatric leukemia|acute myeloid leukemia.*child|naxitamab|dfmo|ch14[:\.]18|gd2|umbilical cord blood|total body irradiation", title):
        tags.add("pediatric-oncology")
    elif any(a in authors for a in PEDI_AUTHORS) and "cancer" in (title + " " + journal):
        tags.add("pediatric-oncology")

    # Adult oncology (cancer but not pediatric)
    if "pediatric-oncology" not in tags and re.search(
            r"melanoma|colorectal|breast cancer|pancreatic|prostate cancer|glioblastoma|biliary|cholangiocarcinoma|hepatocellular|bladder cancer|lung cancer|gastric|colon cancer|rectal|carcinoma|adenocarcinoma|lymphoma|leukemia|myeloma|malignan|oncology|tumor|tumour|chemotherap|immunotherap|metastas|wee1|akt|aldh|aldehyde dehydrogenase|sphingosine|checkpoint|radiosurg|brain metasta",
            title):
        tags.add("adult-oncology")

    # Spinal cord injury
    if re.search(r"spinal cord|paraplegi|tetrapleg|\bsci\b|cord injur|wheelchair|sci-related", title) or any(a in authors for a in SPINAL_AUTHORS):
        tags.add("spinal-cord-injury")

    # Neuroscience / neurodegeneration
    if re.search(r"alzheimer|olfactory|smell|memory impair|dementia|neurodegen|neural|brain|cortex|hippocamp|cognitive|seizure|parkinson|neuroinflamm|neuropharm|glioblastoma|dipg", title):
        tags.add("neuroscience")

    # Sleep (keeps as clinical-research catchall unless combined with genetics)
    if re.search(r"\bsleep\b|insomnia|obstructive sleep apnea|\bosa\b|circadian", title):
        tags.add("clinical-research")

    # Public health / COVID / disparities / primary care / diabetes / surgery etc.
    if re.search(r"covid|sars-cov|pandemic|vaccin|disparit|literacy|refugee|immigrant|food security|prescription produce|burnout|work[- ]family|virtual education|wilderness", title):
        tags.add("clinical-research")

    if re.search(r"diabetes|metabolic syndrome|obesity|cardiometabolic|nutrition|gut microbiom|weight|\bbmi\b|glucose|insulin|glycat|hba1c|satiety|eating", title):
        tags.add("clinical-research")

    if re.search(r"crohn|ileocolectom|diverticul|colectom|inflammatory bowel|\bibd\b|anastomos|surgical site|laparoscop|postoperative|perioperative|hernia|osteoarthr", title) or any(a in authors for a in SURGERY_AUTHORS):
        tags.add("clinical-research")

    if any(a in authors for a in FAMILY_MED_AUTHORS) and "clinical-research" not in tags:
        tags.add("clinical-research")

    # Genetics authors → statistical-genetics if not already tagged
    if any(a in authors for a in GENETICS_AUTHORS) and "statistical-genetics" not in tags:
        # Only if the title looks genetics-ish
        if re.search(r"gene|expression|linkage|plant|bioinformat|chromosom|functional|map|phenotyp|quantitative|biolog", title):
            tags.add("statistical-genetics")

    # ——— Methodology flag ———
    if is_method or journal in METHOD_VENUES:
        tags.add("methodology")

    # Fallback: at least one tag
    if not (tags - {"methodology"}):
        # Pure methodology with no area? leave as is
        # No area → catchall
        if not tags:
            tags.add("clinical-research")

    return sorted(tags)


def merge_keywords(existing: str, new_tags: list[str]) -> str:
    """Merge existing status keywords with new area tags, preserving both."""
    existing_list = [t.strip() for t in (existing or "").split(",") if t.strip()]
    status = [t for t in existing_list if t in STATUS_TAGS]
    # Drop any old area tags and replace with new ones
    new_keywords = sorted(set(status)) + new_tags
    return ", ".join(new_keywords)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Write back to publications.bib")
    args = ap.parse_args()

    if not BIB.exists():
        print(f"Missing: {BIB}", file=sys.stderr)
        return 1

    with BIB.open() as f:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.load(f, parser=parser)

    tag_counter: Counter[str] = Counter()
    per_paper_tag_count = Counter()
    untagged_samples: list[str] = []

    for entry in db.entries:
        new_tags = tag_entry(entry)
        for t in new_tags:
            tag_counter[t] += 1
        per_paper_tag_count[len(new_tags)] += 1
        if len([t for t in new_tags if t != "methodology"]) == 1 and "clinical-research" in new_tags:
            # catchall-only; track a few to show the user
            if len(untagged_samples) < 15:
                untagged_samples.append(
                    f'  [{entry.get("ID","")}] {entry.get("title","")[:120]}'
                )
        entry["keywords"] = merge_keywords(entry.get("keywords", ""), new_tags)

    # Report
    print(f"Total entries: {len(db.entries)}")
    print()
    print("Tag distribution (entry count — one paper can have multiple tags):")
    for t in AREA_TAGS:
        n = tag_counter.get(t, 0)
        print(f"  {t:30s} {n:4d}")
    print()
    print("Tags per paper distribution:")
    for k in sorted(per_paper_tag_count):
        print(f"  {k} tag(s): {per_paper_tag_count[k]} papers")
    print()
    if untagged_samples:
        print("Papers tagged ONLY as 'clinical-research' (catchall — likely need review):")
        for line in untagged_samples:
            print(line)

    if args.write:
        writer = BibTexWriter()
        writer.indent = "\t"
        writer.order_entries_by = None
        with BIB.open("w") as f:
            f.write(writer.write(db))
        print(f"\nWrote tags back to {BIB}")
    else:
        print(f"\n(dry-run — re-run with --write to update {BIB})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
