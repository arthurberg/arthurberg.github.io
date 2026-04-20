#!/usr/bin/env python3
"""Parse Penn State myResearch docx exports into structured YAML.

Reads the two grants exports (Completed Awards + Active Other Support)
from myresearch.psu.edu/ and writes data/grants.yml.

Usage: python3 scripts/parse_grants.py
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC_COMPLETED = ROOT / "myresearch.psu.edu" / "asb17_04-17-2026 053034.docx"
SRC_ACTIVE = ROOT / "myresearch.psu.edu" / "asb17_04-17-2026 053104.docx"
OUT = ROOT / "data" / "grants.yml"


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    # Preserve paragraph breaks then strip tags
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", " ", xml)
    xml = xml.replace("&amp;#39;", "'").replace("&amp;", "&").replace("&quot;", '"')
    xml = re.sub(r"[ \t]+", " ", xml)
    return xml


def parse_completed(text: str) -> list[dict]:
    """Parse the 'Completed Awards' format.

    Each entry has lines:
        Project Title: "..."
        PI: ...
        Sponsor: ...
        Period of Performance: M/D/YYYY-M/D/YYYY
        Total Budget: $X
        Candidate's Role: ...
        Award #: ...
    """
    entries = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r'Project Title:\s*"?(.*?)"?\s*$', line)
        if m:
            if current:
                entries.append(current)
            current = {"title": m.group(1), "status": "completed"}
            continue
        if current is None:
            continue
        if line.startswith("PI:"):
            current["pi"] = line[3:].strip()
        elif line.startswith("Sponsor:"):
            current["sponsor"] = line[8:].strip()
        elif line.startswith("Period of Performance:"):
            period = line.split(":", 1)[1].strip()
            m2 = re.match(r"(\d{1,2}/\d{1,2}/\d{4})-(\d{1,2}/\d{1,2}/\d{4})", period)
            if m2:
                current["start_year"] = int(m2.group(1).split("/")[-1])
                current["end_year"] = int(m2.group(2).split("/")[-1])
            current["period"] = period
        elif line.startswith("Total Budget:"):
            current["budget"] = line.split(":", 1)[1].strip()
        elif line.startswith("Candidate") and "Role" in line:
            current["role"] = line.split(":", 1)[1].strip()
        elif line.startswith("Award #:"):
            current["award_number"] = line.split(":", 1)[1].strip()
    if current:
        entries.append(current)
    return entries


def parse_active(text: str) -> list[dict]:
    """Parse the 'PHS 398 Other Support' format.

    Each entry has:
        *Title: ...
        *Status of Support: Active|Pending
        Project Number: ...
        Name of PD/PI: ...
        *Source of Support: ...
        Project/Proposal Start and End Date: (MM/YYYY): MM/YYYY-MM/YYYY
        * Total Award Amount ...: $X
    """
    entries = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip().lstrip("*").strip()
        if not line:
            continue
        if line.startswith("Title:"):
            if current:
                entries.append(current)
            current = {"title": line[6:].strip()}
            continue
        if current is None:
            continue
        if line.startswith("Status of Support:"):
            status = line.split(":", 1)[1].strip().lower()
            current["status"] = status
        elif line.startswith("Project Number:"):
            current["award_number"] = line.split(":", 1)[1].strip()
        elif line.startswith("Name of PD/PI:"):
            pi_raw = line.split(":", 1)[1].strip()
            # Convert "Last, First" → "First Last"
            if "," in pi_raw:
                last, first = [s.strip() for s in pi_raw.split(",", 1)]
                current["pi"] = f"{first} {last}".strip()
            else:
                current["pi"] = pi_raw
        elif line.startswith("Source of Support:"):
            current["sponsor"] = line.split(":", 1)[1].strip()
        elif "Project/Proposal Start and End Date" in line:
            # The date often appears on the next chunk; pull any MM/YYYY-MM/YYYY pattern
            m2 = re.search(r"(\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{4})", line)
            if m2:
                current["start_year"] = int(m2.group(1).split("/")[-1])
                current["end_year"] = int(m2.group(2).split("/")[-1])
                current["period"] = f"{m2.group(1)}–{m2.group(2)}"
        elif "Total Award Amount" in line:
            m2 = re.search(r"\$[\d,]+", line)
            if m2:
                current["budget"] = m2.group(0)
    if current:
        entries.append(current)
    return entries


def main() -> int:
    completed_text = docx_text(SRC_COMPLETED)
    active_text = docx_text(SRC_ACTIVE)

    completed = parse_completed(completed_text)
    other = parse_active(active_text)

    # Deduplicate: merge by title if completed + other overlap
    all_entries = completed + other

    # Preserve human-maintained extension fields (e.g. `topic` for pending
    # grants) across re-runs by re-reading the existing grants.yml and
    # carrying matching values forward.
    preserved_fields = ("topic",)
    existing: dict[str, dict] = {}
    if OUT.exists():
        with OUT.open() as f:
            for entry in yaml.safe_load(f) or []:
                key = entry.get("award_number") or entry.get("title")
                if key:
                    existing[key] = entry
    for entry in all_entries:
        key = entry.get("award_number") or entry.get("title")
        prev = existing.get(key)
        if prev:
            for field in preserved_fields:
                if field in prev and field not in entry:
                    entry[field] = prev[field]

    # Sort by status (active → pending → completed), then start_year desc
    status_order = {"active": 0, "pending": 1, "completed": 2}
    all_entries.sort(
        key=lambda e: (
            status_order.get(e.get("status", "completed"), 3),
            -(e.get("start_year") or 0),
            e.get("title", ""),
        )
    )

    # For pending grants that have a public-facing `topic`, drop the submitted
    # title before writing to disk — we don't want the specific-aims wording
    # to leak into the public repo via data/grants.yml.
    for entry in all_entries:
        if entry.get("status") == "pending" and entry.get("topic"):
            entry.pop("title", None)

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w") as f:
        f.write("# Auto-generated by scripts/parse_grants.py.\n")
        f.write("# Fields besides `topic` are machine-extracted from myResearch\n")
        f.write("# exports and will be overwritten on re-run. The `topic` field\n")
        f.write("# (optional, used on pending grants to hide the submitted title)\n")
        f.write("# is preserved across re-runs and may be edited by hand.\n")
        f.write("# For any pending grant with a `topic`, the submitted `title`\n")
        f.write("# is intentionally stripped before this file is written.\n")
        yaml.safe_dump(all_entries, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

    print(f"Wrote {OUT} — {len(all_entries)} grants")
    print(f"  active:    {sum(1 for e in all_entries if e.get('status')=='active')}")
    print(f"  pending:   {sum(1 for e in all_entries if e.get('status')=='pending')}")
    print(f"  completed: {sum(1 for e in all_entries if e.get('status')=='completed')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
