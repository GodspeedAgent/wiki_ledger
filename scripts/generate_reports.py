#!/usr/bin/env python3
"""(DEPRECATED) Legacy weekly/monthly report generator.

WikiLedger now uses daily briefs under _briefs/ as the primary insight layer.
This script remains only for reference and should not be used in the daily job.
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
                "entry_name": ep.stem,
                "topic_title": fm.get("topic_title"),
                "normalized_title": fm.get("normalized_title"),
                "rank": int(fm.get("rank", "0") or 0),
                "pageviews": int(fm.get("pageviews", "0") or 0),
                "lead_sentence": fm.get("lead_sentence"),
                "thumbnail_url": fm.get("thumbnail_url"),
                "topic_url": fm.get("topic_url"),
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
    changed = sum(1 for e in entries if e.get("change_type") == "modified")
    top_by_views = sorted(entries, key=lambda e: e["pageviews"], reverse=True)[:6]
    return top_topics, total_views, changed, top_by_views


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

    top_topics, total_views, changed, top_by_views = summarize(week_entries)

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
    cards = [
        "## Top attention\n",
        "<div class=\"grid\">",
    ]
    for e in top_by_views:
        href = f"{{{{ '/entries/{e['entry_name']}/' | relative_url }}}}"
        thumb_url = (e.get("thumbnail_url") or "").strip()
        img = (
            f"<img src=\"{thumb_url}\" alt=\"\" loading=\"lazy\" />"
            if thumb_url and thumb_url.lower() != "null"
            else ""
        )
        title = (e.get("topic_title") or "").replace("\"", "&quot;")
        kicker = f"{e['date'].isoformat()} · Rank {e['rank']} · {e['pageviews']} views"
        cards.append(
            "\n".join(
                [
                    f"<a class=\"card card--link\" href=\"{href}\">",
                    f"  <div class=\"kicker\">{kicker}</div>",
                    f"  <div class=\"card__title\">{title}</div>",
                    f"  <div class=\"thumb\">{img}</div>" if img else "",
                    f"  <div class=\"quote\">{(e.get('lead_sentence') or '')}</div>",
                    "</a>",
                ]
            )
        )
    cards.append("</div>")

    weekly_body = "\n".join(
        [
            "## Highlights\n",
            f"- Entries in period: {len(week_entries)}",
            f"- Total pageviews (sum): {total_views}",
            f"- Modified-sentence events: {changed}",
            "\n## Most frequent topics\n",
        ]
        + [f"- {t} — {c} day(s)" for t, c in top_topics]
        + ["\n" + "\n".join(cards) + "\n"]
        + [
            "## Narrative\n",
            f"This period’s attention concentrates around **{top_topics[0][0]}** (appearing {top_topics[0][1]} time(s) in the sample), with other one-off spikes typical of the top-list feed. A repeat appearance usually signals a sustained news-cycle, a fresh document drop, or a follow-on wave of commentary that sends people to Wikipedia for fast context.\n",
            "\n",
            "A secondary pattern to watch is adjacency: if related pages (people, institutions, places) begin appearing near the same time window, it often indicates a single underlying story branching into sub-threads.\n",
            "\n",
            "## Sources\n",
        ]
        + [f"- {e['topic_url']}" for e in top_by_views if e.get('topic_url')]
        + ["\n"]
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
    top_topics_m, total_views_m, changed_m, top_by_views_m = summarize(month_entries)

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
    cards_m = [
        "## Top attention\n",
        "<div class=\"grid\">",
    ]
    for e in top_by_views_m:
        href = f"{{{{ '/entries/{e['entry_name']}/' | relative_url }}}}"
        thumb_url = (e.get("thumbnail_url") or "").strip()
        img = (
            f"<img src=\"{thumb_url}\" alt=\"\" loading=\"lazy\" />"
            if thumb_url and thumb_url.lower() != "null"
            else ""
        )
        title = (e.get("topic_title") or "").replace("\"", "&quot;")
        kicker = f"{e['date'].isoformat()} · Rank {e['rank']} · {e['pageviews']} views"
        cards_m.append(
            "\n".join(
                [
                    f"<a class=\"card card--link\" href=\"{href}\">",
                    f"  <div class=\"kicker\">{kicker}</div>",
                    f"  <div class=\"card__title\">{title}</div>",
                    f"  <div class=\"thumb\">{img}</div>" if img else "",
                    f"  <div class=\"quote\">{(e.get('lead_sentence') or '')}</div>",
                    "</a>",
                ]
            )
        )
    cards_m.append("</div>")

    monthly_body = "\n".join(
        [
            "## Highlights\n",
            f"- Entries in period: {len(month_entries)}",
            f"- Total pageviews (sum): {total_views_m}",
            f"- Modified-sentence events: {changed_m}",
            "\n## Most frequent topics\n",
        ]
        + [f"- {t} — {c} day(s)" for t, c in top_topics_m]
        + ["\n" + "\n".join(cards_m) + "\n"]
        + [
            "## Narrative\n",
            f"This month’s sample shows a mix of spikes rather than a single unified storyline. The highest-attention entries are often driven by (1) a direct news hook, (2) an anniversary effect, or (3) a media ‘routing’ moment where a widely shared item funnels readers into a reference page.\n",
            "\n",
            "Across the month, recurring topics can be read as persistence of a story-thread; one-offs tend to reflect day-specific events (sports results, entertainment releases, viral clips). Multiple hypotheses can fit the same pattern; the safest read is to treat Wikipedia attention as a proxy for *curiosity with a trigger*, not a vote of approval.\n",
            "\n",
            "## Sources\n",
        ]
        + [f"- {e['topic_url']}" for e in top_by_views_m if e.get('topic_url')]
        + ["\n"]
    )
    write_report(monthly_path, monthly_front, monthly_body)

    print("OK", weekly_path, monthly_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
