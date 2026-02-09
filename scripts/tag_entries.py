#!/usr/bin/env python3
"""Backfill tags for all entries.

Adds/updates front matter keys:
- entity_type
- domain
- tags (1–4 tags)
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
    title = title or ""
    desc = desc or ""
    lead = lead or ""
    text = " ".join([title, desc, lead]).lower()

    # Entity type (use title/desc keywords as well as "is/was" patterns)
    if re.search(r"\b(film|song|album|novel|video game|television series|tv series|miniseries|book)\b", text):
        entity = "work"
    elif re.search(r"\b(country|city|town|village|island|state|province|river|mountain|continent|district|county)\b", desc.lower()):
        entity = "place"
    elif re.search(r"\b(protest|massacre|incident|election|referendum|storm|earthquake|shooting|attack|case|trial|war|battle|final|cup|day)\b", title.lower() + " " + desc.lower()):
        entity = "event"
    elif re.search(r"\b(company|organization|club|team|agency|university|government|committee|association)\b", desc.lower()):
        entity = "org"
    elif re.search(r"\b(was|is) (a|an)\b", lead.lower()) and re.search(
        r"\b(politician|actor|actress|singer|rapper|footballer|player|manager|coach|writer|journalist|financier|socialite|scientist|engineer|quarterback|president)\b",
        text,
    ):
        entity = "person"
    else:
        # fallback heuristic: many biographies follow "X is/was a" even without a profession match
        entity = "person" if re.match(r"^[A-Z][^,]{2,80} was an? ", lead) else "other"

    # Domain (primary)
    if re.search(r"\b(football|soccer|cricket|nba|nfl|mlb|premier league|fa cup|coach|manager|quarterback|goal|match)\b", text):
        domain = "sports"
    elif re.search(r"\b(film|movie|tv|television|series|album|song|rapper|singer|actor|actress|netflix|super bowl|halftime)\b", text):
        domain = "entertainment"
    elif re.search(r"\b(murder|rape|sex offender|traffick|trial|court|arrest|fraud|crime|criminal|abuse)\b", text):
        domain = "crime"
    elif re.search(r"\b(election|president|prime minister|parliament|senate|congress|party|government|minister|coup)\b", text):
        domain = "politics"
    elif re.search(r"\b(software|internet|domain|protocol|computer|website|app|cyber)\b", text):
        domain = "tech"
    elif re.search(r"\b(century|dynasty|ancient|historical|massacre|protests|revolution)\b", text):
        domain = "history"
    elif re.search(r"\b(science|physics|chemistry|biology|astronomy|space|nasa|medicine|disease)\b", text):
        domain = "science"
    else:
        domain = "news"

    # Secondary tags (0–2), keep total <= 4
    extra = []
    if re.search(r"\b(court|trial|judge|lawsuit|indictment|doj|fbi)\b", text):
        extra.append("legal")
    if re.search(r"\b(internet|domain|website|protocol|tld)\b", text):
        extra.append("internet")
    if re.search(r"\b(china|tiananmen)\b", text):
        extra.append("china")
    if re.search(r"\b(super bowl|halftime)\b", text):
        extra.append("superbowl")

    tags = []
    for t in [domain, entity] + extra:
        if t and t not in tags:
            tags.append(t)
        if len(tags) >= 4:
            break

    return entity, domain, tags


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

        entity, domain, tags = classify(title, desc, lead)

        new = txt
        new = upsert_front_matter(p, "entity_type", entity, new)
        new = upsert_front_matter(p, "domain", domain, new)
        # YAML list for tags (1–4 values)
        if re.search(r"^tags:\s*$", new, flags=re.M):
            pass
        elif re.search(r"^tags:\s*\[.*\]\s*$", new, flags=re.M):
            new = re.sub(r"^tags:\s*\[.*\]\s*$", "tags: [" + ", ".join('"'+t+'"' for t in tags) + "]", new, flags=re.M)
        else:
            # insert as inline list
            new = upsert_front_matter(p, "tags", "[" + ", ".join(tags) + "]", new)
            # upsert_front_matter quotes the whole value; fix to raw YAML list
            new = re.sub(r"^tags: \"\[(.*)\]\"$", r"tags: [\1]", new, flags=re.M)

        new = upsert_front_matter(p, "tags_version", TAGS_VERSION, new)

        if new != txt:
            p.write_text(new, encoding="utf-8")
            changed += 1

    print("tagged", changed)


if __name__ == "__main__":
    main()
