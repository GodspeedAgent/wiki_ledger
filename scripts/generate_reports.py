#!/usr/bin/env python3
"""Generate weekly + monthly report markdown pages under _reports/.

LLM-generated narrative should be written by the agent; this script focuses on
assembling stats & a stable structure the agent can fill/extend.

No dependencies.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import re
from collections import Counter, defaultdict
from pathlib import Path

REPORTS_DIR = Path("_reports")
ENTRIES_DIR = Path("_entries")


def yq(s):
    if s is None:
        return "null"
    s = str(s).replace("\\", "\\\\").replace('"', "\\\"")
    return '"' + s + '"'


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
            fm[k] = v
    return fm


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "report"


def load_entries():
    entries = []
    for ep in ENTRIES_DIR.glob("*.md"):
        fm = read_front(ep)
        if not fm.get("date"):
            continue
        d = _dt.date.fromisoformat(fm["date"])
        entries.append(
            {
                "date": d,
                "topic_title": fm.get("topic_title"),
                "normalized_title": fm.get("normalized_title"),
                "rank": int(fm.get("rank", "0") or 0),
                "pageviews": int(fm.get("pageviews", "0") or 0),
                "sentence_changed": fm.get("sentence_changed") == "true",
                "change_type": fm.get("change_type"),
            }
        )
    return sorted(entries, key=lambda e: e["date"])


def iso_week_start(d: _dt.date) -> _dt.date:
    return d - _dt.timedelta(days=d.weekday())


def month_start(d: _dt.date) -> _dt.date:
    return _dt.date(d.year, d.month, 1)


def month_end(d: _dt.date) -> _dt.date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return _dt.date(d.year, d.month, last_day)


def ensure_dir():
    REPORTS_DIR.mkdir(exist_ok=True)


def write_report(path: Path, front: dict, body: str):
    lines = ["---"]
    for k, v in front.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {yq(v)}")
    lines += ["---", "", body.strip() + "\n"]
    path.write_text("\n".join(lines), encoding="utf-8")


def summarize(entries):
    # simple counters
    topics = [e["normalized_title"] or e["topic_title"] for e in entries]
    topic_counts = Counter(topics)
    top_topics = topic_counts.most_common(10)
    total_views = sum(e["pageviews"] for e in entries)
    changed = sum(1 for e in entries if e["change_type"] == "modified")
    return top_topics, total_views, changed


def main():
    ensure_dir()
    all_entries = load_entries()
    if not all_entries:
        print("No entries")
        return 0

    latest = all_entries[-1]["date"]

    # Prefer the most recent completed periods so reports feel meaningful.
    anchor = latest - _dt.timedelta(days=1)

    # weekly: week containing anchor; if too sparse, step back one week.
    ws = iso_week_start(anchor)
    we = ws + _dt.timedelta(days=6)
    week_entries = [e for e in all_entries if ws <= e["date"] <= we]
    if len({e["date"] for e in week_entries}) < 4:
        ws = ws - _dt.timedelta(days=7)
        we = ws + _dt.timedelta(days=6)
        week_entries = [e for e in all_entries if ws <= e["date"] <= we]

    top_topics, total_views, changed = summarize(week_entries)

    weekly_name = f"weekly-{ws.isoformat()}"
    weekly_path = REPORTS_DIR / f"{weekly_name}.md"
    weekly_front = {
        "layout": "report",
        "title": f"Weekly insights ({ws.isoformat()})",
        "report_kind": "weekly",
        "period_start": ws.isoformat(),
        "period_end": we.isoformat(),
        "summary": f"Top themes and connections for the week of {ws.isoformat()}.",
    }
    weekly_body = "\n".join(
        [
            "## Highlights\n",
            f"- Entries in period: {len(week_entries)}",
            f"- Total pageviews (sum): {total_views}",
            f"- Modified-sentence events: {changed}",
            "\n## Most frequent topics\n",
        ]
        + [f"- {t} — {c} day(s)" for t, c in top_topics]
        + [
            "\n## Narrative (LLM)\n",
            "(Fill: why these topics likely spiked; what connects them; what to watch next.)\n",
            "## Sources\n",
            "(Fill: 5–10 supporting links from web search.)\n",
        ]
    )
    write_report(weekly_path, weekly_front, weekly_body)

    # monthly: month containing anchor; if too sparse, step back one month.
    ms = month_start(anchor)
    me = month_end(anchor)
    month_entries = [e for e in all_entries if ms <= e["date"] <= me]
    if len({e["date"] for e in month_entries}) < 10:
        # previous month
        prev = (ms - _dt.timedelta(days=1))
        ms = month_start(prev)
        me = month_end(prev)
        month_entries = [e for e in all_entries if ms <= e["date"] <= me]
    top_topics_m, total_views_m, changed_m = summarize(month_entries)

    monthly_name = f"monthly-{ms.isoformat()[:7]}"
    monthly_path = REPORTS_DIR / f"{monthly_name}.md"
    monthly_front = {
        "layout": "report",
        "title": f"Monthly insights ({ms.isoformat()[:7]})",
        "report_kind": "monthly",
        "period_start": ms.isoformat(),
        "period_end": me.isoformat(),
        "summary": f"What captured attention in {ms.isoformat()[:7]} — with connections and context.",
    }
    monthly_body = "\n".join(
        [
            "## Highlights\n",
            f"- Entries in period: {len(month_entries)}",
            f"- Total pageviews (sum): {total_views_m}",
            f"- Modified-sentence events: {changed_m}",
            "\n## Most frequent topics\n",
        ]
        + [f"- {t} — {c} day(s)" for t, c in top_topics_m]
        + [
            "\n## Narrative (LLM)\n",
            "(Fill: biggest storylines; recurring motifs; surprising spikes.)\n",
            "## Sources\n",
            "(Fill: 10–20 supporting links from web search.)\n",
        ]
    )
    write_report(monthly_path, monthly_front, monthly_body)

    print("OK", weekly_path, monthly_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
