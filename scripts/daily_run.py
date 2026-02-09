#!/usr/bin/env python3
"""WikiLedger daily ingestion.

Fetch yesterday's Wikimedia Top Articles list and create 3 entries (weighted random,
no replacement) using Wikipedia REST Summary.

Designed for GitHub Pages/Jekyll: writes markdown files into _entries/ and updates
or creates topic pages in _topics/.

No external dependencies.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import random
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import requests

LANG = "en"
PROJECT = "wikipedia"
ACCESS = "all-access"
AGENT_NAME = "wikiledger"
AGENT_VERSION = "1.0.0"

ENTRIES_DIR = Path("_entries")
TOPICS_DIR = Path("_topics")

USER_AGENT = "WikiLedgerBot/1.0"


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
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "topic"


def is_normal(title: str) -> bool:
    if title == "Main_Page":
        return False
    if title.startswith(("Special:", "File:", "Talk:", "User:")):
        return False
    return True


def first_declarative(extract: str) -> str | None:
    text = re.sub(r"\s+", " ", (extract or "").strip())
    for m in re.finditer(r"\.(?:\s|$)", text):
        sent = text[: m.end()].strip()
        if len(sent) < 20:
            continue
        if not re.search(r"[A-Za-z]", sent):
            continue
        return sent
    return None


def get_json(session: requests.Session, url: str, *, tries: int = 6, timeout: int = 30):
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json(), r.headers.get("x-request-id", ""), 200
            if r.status_code == 404:
                return None, r.headers.get("x-request-id", ""), 404
            if r.status_code in (429, 500, 502, 503, 504):
                last = r.status_code
                time.sleep(1.2 * (i + 1))
                continue
            r.raise_for_status()
        except Exception as e:
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


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


@dataclass
class Picked:
    rank: int
    pageviews: int
    article: str
    top_articles_date: _dt.date


def fetch_top_for(entry_date: _dt.date, session: requests.Session) -> tuple[list[dict], str, _dt.date]:
    """Return top articles json list for a day near (entry_date-1).

    API often lags; we fall back up to 7 days.
    """
    top_day = entry_date - _dt.timedelta(days=1)
    for back in range(0, 8):
        day_try = top_day - _dt.timedelta(days=back)
        url = (
            f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
            f"{LANG}.{PROJECT}/{ACCESS}/{day_try.year:04d}/{day_try.month:02d}/{day_try.day:02d}"
        )
        js, trace, code = get_json(session, url)
        if code == 200:
            return js["items"][0]["articles"], trace, day_try
    raise RuntimeError(f"No top list found for {entry_date} (tried back 7d)")


def weighted_sample_without_replacement(pop, weights, k, rng: random.Random):
    chosen = []
    pool = list(pop)
    w = list(weights)
    for _ in range(min(k, len(pool))):
        total = sum(w)
        r = rng.random() * total
        acc = 0.0
        idx = 0
        for i, wi in enumerate(w):
            acc += wi
            if acc >= r:
                idx = i
                break
        chosen.append(pool.pop(idx))
        w.pop(idx)
    return chosen


def main():
    ENTRIES_DIR.mkdir(exist_ok=True)
    TOPICS_DIR.mkdir(exist_ok=True)

    today = _dt.date.today()  # host local date; OK for daily schedule

    # Abort if we already have an entry for today
    for ep in ENTRIES_DIR.glob("*.md"):
        fm = read_front(ep)
        if fm.get("date") == today.isoformat():
            print("ABORT: today already has an entry")
            return 0

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    arts, trace_top, top_day_used = fetch_top_for(today, session)

    cand = [a for a in arts if is_normal(a.get("article", ""))][:100]
    if len(cand) < 3:
        raise RuntimeError("Not enough candidates in top 100")

    weights = [1.0 / max(1, int(a["rank"])) for a in cand]

    rng = random.Random(int(today.strftime("%Y%m%d")))

    # Weighted random pick from top 100 (single entry)
    pick = rng.choices(cand, weights=weights, k=1)[0]

    # Resolve summary; if sentence extraction fails, retry deterministically.
    attempts = 0
    while True:
        attempts += 1
        if attempts > 25:
            raise RuntimeError("Too many attempts to build entry")

        article = pick["article"]
        url_sum = f"https://{LANG}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(article, safe='')}"
        sumj, trace_sum, code = get_json(session, url_sum)
        if code == 200:
            sent = first_declarative(sumj.get("extract"))
            if sent:
                lead_sentence = sent
                break

        rng2 = random.Random(int(today.strftime("%Y%m%d")) + attempts)
        pick = rng2.choices(cand, weights=weights, k=1)[0]

    picks = [(pick, sumj, trace_sum, lead_sentence)]

    # Create entries and update topics incrementally
    # NOTE: topic pages are append-only; sentence_changed compares to last occurrence in that topic.

    # index.md is liquid-driven; no need to append.

    for pick, sumj, trace_sum, lead_sentence in picks:
        rank = int(pick["rank"])
        pageviews = int(pick["views"])

        canonical_title = sumj.get("title") or pick["article"].replace("_", " ")
        normalized_title = (sumj.get("titles", {}) or {}).get("normalized") or canonical_title
        topic_slug = slugify(normalized_title)

        page_id = sumj.get("pageid")
        rev_id = sumj.get("revision")
        namespace_id = sumj.get("ns")
        if namespace_id is None:
            namespace_id = 0
        article_type = sumj.get("type")
        desc = sumj.get("description")
        desc_src = "wikipedia_rest_summary" if desc else None
        wikibase = sumj.get("wikibase_item")
        content_urls = (sumj.get("content_urls", {}) or {}).get("desktop", {})
        topic_url = content_urls.get("page") or ((sumj.get("content_urls", {}) or {}).get("mobile", {}) or {}).get("page")
        thumb = sumj.get("thumbnail") or {}
        orig = sumj.get("originalimage") or {}

        sentence_hash = hashlib.sha256(lead_sentence.encode("utf-8")).hexdigest()
        sentence_length = len(lead_sentence)

        topic_path = TOPICS_DIR / f"{topic_slug}.md"

        # Read topic history (minimal)
        times_seen_total = 1
        first_seen = today
        days_since_last_seen = None
        sentence_changed = True
        change_type = "first_seen"
        sentence_changed_count = 1
        hist = []

        if topic_path.exists():
            tfm = read_front(topic_path)
            times_seen_total = int(tfm.get("times_seen_total", "1")) + 1
            sentence_changed_count = int(tfm.get("sentence_changed_count", "0"))

            # parse existing sentence_history dates + hashes
            raw = topic_path.read_text(encoding="utf-8").splitlines()
            in_hist = False
            current = None
            for line in raw:
                if line.strip() == "sentence_history:":
                    in_hist = True
                    continue
                if not in_hist:
                    continue
                if line.strip() == "---":
                    break
                if line.startswith("  - "):
                    if current:
                        hist.append(current)
                    current = {}
                    line2 = line[4:]
                    if ": " in line2:
                        k, v = line2.split(": ", 1)
                        hist[-1:]  # noop
                        current[k] = v.strip().strip('"')
                elif line.startswith("    ") and current is not None:
                    l = line.strip()
                    if ": " in l:
                        k, v = l.split(": ", 1)
                        current[k] = v.strip().strip('"')
            if current:
                hist.append(current)

            if hist:
                first_seen = _dt.date.fromisoformat(hist[0]["date"])
                last_date = _dt.date.fromisoformat(hist[-1]["date"])
                days_since_last_seen = (today - last_date).days
                if hist[-1].get("sentence_hash") == sentence_hash:
                    sentence_changed = False
                    change_type = "unchanged"
                else:
                    sentence_changed = True
                    change_type = "modified"
                    sentence_changed_count += 1
            else:
                sentence_changed_count = 1

        fetch_timestamp = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        request_trace_id = trace_sum or trace_top

        # filename must be unique (3 per day)
        entry_name = f"{today.isoformat()}--{topic_slug}.md"
        entry_path = ENTRIES_DIR / entry_name

        fm = [
            "---",
            yaml_kv("layout", "entry"),
            yaml_kv("title", canonical_title),
            yaml_kv("date", today.isoformat()),
            yaml_kv("topic_title", canonical_title),
            yaml_kv("topic_page_id", page_id),
            yaml_kv("wikibase_item", wikibase),
            yaml_kv("topic_url", topic_url),
            yaml_kv("language", LANG),
            yaml_kv("namespace_id", namespace_id),
            yaml_kv("article_type", article_type),
            yaml_kv("description", desc),
            yaml_kv("description_source", desc_src),
            yaml_kv("canonical_title", canonical_title),
            yaml_kv("normalized_title", normalized_title),
            yaml_kv("rank", rank),
            yaml_kv("pageviews", pageviews),
            yaml_kv("times_seen_total", times_seen_total),
            yaml_kv("first_seen", first_seen.isoformat()),
            yaml_kv("days_since_last_seen", days_since_last_seen),
            yaml_kv("lead_sentence", lead_sentence),
            yaml_kv("sentence_hash", sentence_hash),
            yaml_kv("sentence_length", sentence_length),
            yaml_kv("sentence_changed", bool(sentence_changed)),
            yaml_kv("change_type", change_type),
            yaml_kv("source_revision_id", rev_id),
            yaml_kv("fetch_timestamp", fetch_timestamp),
            yaml_kv("request_trace_id", request_trace_id),
            yaml_kv("api_endpoint", "wikipedia_rest_summary"),
            yaml_kv("thumbnail_url", thumb.get("source")),
            yaml_kv("thumbnail_width", thumb.get("width")),
            yaml_kv("thumbnail_height", thumb.get("height")),
            yaml_kv("original_image_url", orig.get("source")),
            yaml_kv("agent_name", AGENT_NAME),
            yaml_kv("agent_version", AGENT_VERSION),
            yaml_kv("top_articles_date", top_day_used.isoformat()),
            "---",
            "",
        ]

        entry_path.write_text("\n".join(fm), encoding="utf-8")

        # Rewrite topic page with appended history
        hist.append(
            {
                "date": today.isoformat(),
                "rank": rank,
                "pageviews": pageviews,
                "lead_sentence": lead_sentence,
                "sentence_hash": sentence_hash,
                "change_type": change_type,
                "source_revision_id": int(rev_id or 0),
            }
        )

        out = [
            "---",
            yaml_kv("layout", "topic"),
            yaml_kv("title", canonical_title),
            yaml_kv("topic_title", canonical_title),
            yaml_kv("topic_page_id", page_id),
            yaml_kv("wikibase_item", wikibase),
            yaml_kv("topic_url", topic_url),
            yaml_kv("language", LANG),
            yaml_kv("namespace_id", namespace_id),
            yaml_kv("article_type", article_type),
            yaml_kv("description", desc),
            yaml_kv("description_source", desc_src),
            yaml_kv("canonical_title", canonical_title),
            yaml_kv("normalized_title", normalized_title),
            yaml_kv("times_seen_total", len(hist)),
            yaml_kv("sentence_changed_count", sentence_changed_count),
            "sentence_history:",
        ]
        for item in hist:
            out.append(f"  - date: {yq(item['date'])}")
            out.append(f"    rank: {int(item['rank'])}")
            out.append(f"    pageviews: {int(item['pageviews'])}")
            out.append(f"    lead_sentence: {yq(item['lead_sentence'])}")
            out.append(f"    sentence_hash: {yq(item['sentence_hash'])}")
            out.append(f"    change_type: {yq(item['change_type'])}")
            out.append(f"    source_revision_id: {int(item['source_revision_id'])}")
        out += ["---", ""]

        topic_path.write_text("\n".join(out), encoding="utf-8")

    print("OK: wrote 1 entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
