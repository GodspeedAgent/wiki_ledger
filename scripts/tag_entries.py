#!/usr/bin/env python3
"""Backfill tags for all entries.

Adds/updates front matter keys:
- entity_type
- domain
- tags_version

No external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

ENTRIES_DIR = Path("_entries")
TAGS_VERSION = "v1"


def read_front(path: Path) -> tuple[dict, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines
    fm = {}
    out = []
    out.append(lines[0])
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            break
        if ": " in line:
            k, v = line.split(": ", 1)
            fm[k.strip()] = v.strip().strip('"')
        out.append(line)
        i += 1
    # include closing --- and rest
    rest = lines[i:]
    return fm, rest


def classify(title: str, desc: str, lead: str):
    text = " ".join([title or "", desc or "", lead or ""]).lower()

    # Entity type
    if re.search(r"\bis a (film|song|album|novel|video game|television series|tv series|miniseries|book)\b", text):
        entity = "work"
    elif re.search(r"\bis (a|an) (country|city|town|village|island|state|province|river|mountain|continent)\b", text):
        entity = "place"
    elif re.search(r"\b(was|is) (a|an) (battle|war|protest|massacre|incident|election|referendum|storm|earthquake|shooting|attack|case)\b", text):
        entity = "event"
    elif re.search(r"\bis (a|an) (company|organization|club|team|agency|university|government department)\b", text):
        entity = "org"
    elif re.search(r"\b(was|is) (a|an) (politician|actor|actress|singer|rapper|footballer|player|manager|coach|writer|journalist|financier|socialite|scientist|engineer)\b", text):
        entity = "person"
    else:
        entity = "other"

    # Domain
    if re.search(r"\b(football|soccer|cricket|nba|nfl|mlb|premier league|coach|manager|quarterback|goal|match)\b", text):
        domain = "sports"
    elif re.search(r"\b(film|movie|tv|television|series|album|song|rapper|singer|actor|actress|netflix)\b", text):
        domain = "entertainment"
    elif re.search(r"\b(murder|rape|sex offender|traffick|trial|court|arrest|fraud|crime|criminal)\b", text):
        domain = "crime"
    elif re.search(r"\b(election|president|prime minister|parliament|senate|congress|party|government|minister)\b", text):
        domain = "politics"
    elif re.search(r"\b(software|internet|domain|protocol|ai|chatgpt|computer|website|app)\b", text):
        domain = "tech"
    elif re.search(r"\b(century|massacre|protests|revolution|dynasty|ancient|historical)\b", text):
        domain = "history"
    elif re.search(r"\b(science|physics|chemistry|biology|astronomy|space|nasa|medicine)\b", text):
        domain = "science"
    else:
        domain = "news"

    return entity, domain


def upsert_front_matter(path: Path, key: str, value: str, raw_text: str) -> str:
    # replace existing line
    if re.search(rf"^{re.escape(key)}:\s*.*$", raw_text, flags=re.M):
        return re.sub(rf"^{re.escape(key)}:\s*.*$", f"{key}: \"{value}\"", raw_text, flags=re.M)

    # insert before closing --- of front matter
    parts = raw_text.split("---", 2)
    if len(parts) < 3:
        return raw_text
    head = parts[0] + "---\n" + parts[1].lstrip("\n")
    tail = "---" + parts[2]
    if not head.endswith("\n"):
        head += "\n"
    head += f"{key}: \"{value}\"\n"
    return head + tail


def main():
    changed = 0
    for p in ENTRIES_DIR.glob("*.md"):
        txt = p.read_text(encoding="utf-8")
        fm = {}
        if txt.startswith("---"):
            for line in txt.split("---", 2)[1].splitlines():
                if ": " in line:
                    k, v = line.split(": ", 1)
                    fm[k.strip()] = v.strip().strip('"')
        title = fm.get("topic_title", "")
        desc = fm.get("description", "")
        lead = fm.get("lead_sentence", "")

        entity, domain = classify(title, desc, lead)

        new = txt
        new = upsert_front_matter(p, "entity_type", entity, new)
        new = upsert_front_matter(p, "domain", domain, new)
        new = upsert_front_matter(p, "tags_version", TAGS_VERSION, new)

        if new != txt:
            p.write_text(new, encoding="utf-8")
            changed += 1

    print("tagged", changed)


if __name__ == "__main__":
    main()
