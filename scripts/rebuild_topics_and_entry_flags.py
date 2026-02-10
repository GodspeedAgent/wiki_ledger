#!/usr/bin/env python3
"""Rebuild topic pages and recompute per-entry change fields.

Why: Backfill/regeneration passes can leave entry metadata inconsistent (e.g.
`sentence_changed: true` while the topic history shows unchanged).

This script:
1) Scans all _entries/*.md chronologically.
2) Recomputes these fields per entry (based on prior appearances of the same normalized_title):
   - times_seen_total
   - first_seen
   - days_since_last_seen
   - sentence_changed
   - change_type (first_seen|unchanged|modified)
3) Rewrites _topics/*.md from scratch (append-only guarantee intentionally waived for this repair).

No external dependencies.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

ENTRIES_DIR = Path("_entries")
TOPICS_DIR = Path("_topics")


def yq(s):
    if s is None:
        return "null"
    s = str(s).replace("\\", "\\\\").replace('"', "\\\"")
    return '"' + s + '"'


def yaml_kv(k, v):
    if isinstance(v, bool):
        return f"{k}: {'true' if v else 'false'}"
    if isinstance(v, (int, float)):
        return f"{k}: {v}"
    if v is None:
        return f"{k}: null"
    return f"{k}: {yq(v)}"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "topic"


def read_front(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    fm = {}
    if not lines or lines[0].strip() != "---":
        return fm
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ": " in line:
            k, v = line.split(": ", 1)
            v = v.strip()
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1].replace('\\"', '"').replace('\\\\', "\\")
            fm[k.strip()] = v
    return fm


def set_key(txt: str, key: str, value_yaml: str) -> str:
    # Replace if exists
    if re.search(rf"^{re.escape(key)}:\s*.*$", txt, flags=re.M):
        return re.sub(rf"^{re.escape(key)}:\s*.*$", f"{key}: {value_yaml}", txt, flags=re.M)

    # Insert before closing front matter ---
    if not txt.startswith("---"):
        return txt
    parts = txt.split("---", 2)
    if len(parts) < 3:
        return txt
    head = "---\n" + parts[1].lstrip("\n")
    tail = "---" + parts[2]
    if not head.endswith("\n"):
        head += "\n"
    head += f"{key}: {value_yaml}\n"
    return head + tail


def main():
    TOPICS_DIR.mkdir(exist_ok=True)

    entries = []
    for ep in ENTRIES_DIR.glob("*.md"):
        fm = read_front(ep)
        if not fm.get("date"):
            continue
        try:
            d = _dt.date.fromisoformat(fm["date"])
        except Exception:
            continue
        norm = fm.get("normalized_title") or fm.get("topic_title")
        if not norm:
            continue
        entries.append((d, ep, fm))

    entries.sort(key=lambda t: (t[0], t[1].name))

    # Recompute per-topic state
    state = {}
    topic_hist = {}  # key -> list of history items

    patched = 0

    for d, ep, fm in entries:
        key = (fm.get("normalized_title") or fm.get("topic_title") or "").lower()
        # Prefer paragraph_hash for change detection when available
        sh = fm.get("paragraph_hash") or fm.get("sentence_hash") or ""
        st = state.get(key)
        if st is None:
            first_seen = d
            times = 1
            days_since = None
            sentence_changed = True
            change_type = "first_seen"
            changed_count = 1
            last_hash = sh
            last_date = d
        else:
            first_seen = st["first_seen"]
            times = st["times"] + 1
            days_since = (d - st["last_date"]).days
            if sh and sh == st["last_hash"]:
                sentence_changed = False
                change_type = "unchanged"
                changed_count = st["changed_count"]
            else:
                sentence_changed = True
                change_type = "modified"
                changed_count = st["changed_count"] + 1
            last_hash = sh or st["last_hash"]
            last_date = d

        state[key] = {
            "first_seen": first_seen,
            "times": times,
            "last_date": last_date,
            "last_hash": last_hash,
            "changed_count": changed_count,
        }

        # Patch entry file
        txt = ep.read_text(encoding="utf-8")
        txt2 = txt
        txt2 = set_key(txt2, "times_seen_total", str(times))
        txt2 = set_key(txt2, "first_seen", yq(first_seen.isoformat()))
        txt2 = set_key(txt2, "days_since_last_seen", "null" if days_since is None else str(days_since))
        txt2 = set_key(txt2, "sentence_changed", "true" if sentence_changed else "false")
        txt2 = set_key(txt2, "change_type", yq(change_type))

        if txt2 != txt:
            ep.write_text(txt2, encoding="utf-8")
            patched += 1

        # Save history item for topic page
        hist = topic_hist.setdefault(key, [])
        hist.append(
            {
                "date": d.isoformat(),
                "rank": int(fm.get("rank", "0") or 0),
                "pageviews": int(fm.get("pageviews", "0") or 0),
                "lead_sentence": fm.get("lead_sentence") or "",
                "lead_paragraph": fm.get("lead_paragraph") or fm.get("lead_sentence") or "",
                "sentence_hash": fm.get("sentence_hash") or "",
                "paragraph_hash": sh,
                "change_type": change_type,
                "source_revision_id": int(fm.get("source_revision_id", "0") or 0),
                # carry a few useful bits
                "topic_title": fm.get("topic_title") or fm.get("canonical_title") or "",
                "topic_page_id": fm.get("topic_page_id"),
                "wikibase_item": fm.get("wikibase_item"),
                "topic_url": fm.get("topic_url"),
                "language": fm.get("language"),
                "namespace_id": int(fm.get("namespace_id", "0") or 0),
                "article_type": fm.get("article_type"),
                "description": fm.get("description"),
                "description_source": fm.get("description_source"),
                "canonical_title": fm.get("canonical_title"),
                "normalized_title": fm.get("normalized_title") or fm.get("topic_title"),
            }
        )

    # Rebuild topics directory
    for tp in TOPICS_DIR.glob("*.md"):
        tp.unlink()

    for key, hist in topic_hist.items():
        # Use last item as metadata source
        last = hist[-1]
        slug = slugify(last.get("normalized_title") or last.get("topic_title"))
        st = state[key]

        out = [
            "---",
            yaml_kv("layout", "topic"),
            yaml_kv("title", last.get("canonical_title") or last.get("topic_title")),
            yaml_kv("topic_title", last.get("topic_title")),
            yaml_kv("topic_page_id", last.get("topic_page_id")),
            yaml_kv("wikibase_item", last.get("wikibase_item")),
            yaml_kv("topic_url", last.get("topic_url")),
            yaml_kv("language", last.get("language")),
            yaml_kv("namespace_id", last.get("namespace_id")),
            yaml_kv("article_type", last.get("article_type")),
            yaml_kv("description", last.get("description")),
            yaml_kv("description_source", last.get("description_source")),
            yaml_kv("canonical_title", last.get("canonical_title")),
            yaml_kv("normalized_title", last.get("normalized_title")),
            yaml_kv("times_seen_total", st["times"]),
            yaml_kv("sentence_changed_count", st["changed_count"]),
            "sentence_history:",
        ]
        for item in hist:
            out.append(f"  - date: {yq(item['date'])}")
            out.append(f"    rank: {int(item['rank'])}")
            out.append(f"    pageviews: {int(item['pageviews'])}")
            out.append(f"    lead_sentence: {yq(item['lead_sentence'])}")
            out.append(f"    lead_paragraph: {yq(item.get('lead_paragraph') or item['lead_sentence'])}")
            out.append(f"    sentence_hash: {yq(item['sentence_hash'])}")
            out.append(f"    paragraph_hash: {yq(item['sentence_hash'])}")
            out.append(f"    change_type: {yq(item['change_type'])}")
            out.append(f"    source_revision_id: {int(item['source_revision_id'])}")
        out += ["---", ""]

        (TOPICS_DIR / f"{slug}.md").write_text("\n".join(out), encoding="utf-8")

    print(f"OK patched_entries={patched} topics={len(topic_hist)}")


if __name__ == "__main__":
    raise SystemExit(main())
