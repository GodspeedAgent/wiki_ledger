#!/usr/bin/env python3
"""Generate a tight daily 'Today’s Trend Brief' page.

- Pulls yesterday's top-articles list.
- Selects 10 weighted-random articles from top 100 (no replacement).
- Fetches Wikipedia REST summary for each.
- Writes one brief file under _briefs/.

This is intentionally lightweight and deterministic; deeper narrative can be
edited later or extended with web-search enrichment.

No external dependencies.
"""

from __future__ import annotations

import datetime as _dt
import random
import re
import time
import urllib.parse
from pathlib import Path

import requests

LANG = 'en'
PROJECT = 'wikipedia'
ACCESS = 'all-access'
USER_AGENT = 'WikiLedgerBot/1.0'
COMMUNITY_USER_AGENT = 'WikiLedgerBot/1.0 (daily brief; contact: none)'
BRAVE_USER_AGENT = 'WikiLedgerBot/1.0 (brave search; daily brief)'
BRIEFS_DIR = Path('_briefs')


def yq(s):
    if s is None:
        return 'null'
    s = str(s).replace('\\', '\\\\').replace('"', '\\"')
    return '"' + s + '"'


def first_paragraph(extract: str) -> str:
    raw = (extract or '').strip()
    if not raw:
        return ''
    parts = re.split(r'\n\s*\n', raw)
    para = parts[0] if parts else raw
    para = para.split('\n', 1)[0]
    return re.sub(r'\s+', ' ', para).strip()


def first_declarative(paragraph: str) -> str:
    text = re.sub(r'\s+', ' ', (paragraph or '').strip())
    for m in re.finditer(r'\.(?:\s|$)', text):
        sent = text[: m.end()].strip()
        if len(sent) >= 20 and re.search(r'[A-Za-z]', sent):
            return sent
    return text


def is_normal(title: str) -> bool:
    if title == 'Main_Page':
        return False
    if title.startswith(('Special:', 'File:', 'Talk:', 'User:')):
        return False
    return True


def get_json(session: requests.Session, url: str, tries: int = 6, timeout: int = 30):
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json(), 200
            if r.status_code == 404:
                return None, 404
            if r.status_code in (429, 500, 502, 503, 504):
                last = r.status_code
                time.sleep(1.2 * (i + 1))
                continue
            r.raise_for_status()
        except Exception as e:
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f'GET failed {url}: {last}')


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


def search_community_sources(session: requests.Session, query: str, limit: int = 3):
    """Search public community discussion JSON for corroborating chatter.

    Uses unauthenticated endpoints; keep it small + throttled.
    """
    q = (query or '').strip()
    if not q:
        return []

    url = (
        'https://www.reddit.com/r/all/search.json?'
        + urllib.parse.urlencode({
            'q': q,
            'restrict_sr': 'false',
            'sort': 'top',
            't': 'day',
            'limit': str(max(1, min(10, limit))),
        })
    )

    try:
        old_ua = session.headers.get('User-Agent')
        session.headers['User-Agent'] = COMMUNITY_USER_AGENT
        js, code = get_json(session, url, tries=3, timeout=15)
        if code != 200 or not js:
            return []
        posts = []
        for ch in (js.get('data', {}) or {}).get('children', [])[:limit]:
            d = (ch or {}).get('data') or {}
            permalink = d.get('permalink')
            if not permalink:
                continue
            posts.append({
                'title': d.get('title') or 'Community post',
                'subreddit': d.get('subreddit') or 'unknown',
                'score': d.get('score'),
                'url': 'https://www.reddit.com' + permalink,
            })
        return posts
    except Exception:
        return []
    finally:
        try:
            if old_ua:
                session.headers['User-Agent'] = old_ua
        except Exception:
            pass


def brave_web_search(session: requests.Session, query: str, limit: int = 3):
    """Optional: Brave web search if BRAVE_API_KEY is set.

    Returns [{title, url, description}]. Throttling is caller's responsibility.
    """
    import os

    api_key = os.environ.get('BRAVE_API_KEY')
    q = (query or '').strip()
    if not api_key or not q:
        return []

    url = 'https://api.search.brave.com/res/v1/web/search?' + urllib.parse.urlencode({
        'q': q,
        'count': str(max(1, min(10, limit))),
        'safesearch': 'moderate',
        'freshness': 'pd',
        'text_decorations': 'false',
    })

    try:
        old_ua = session.headers.get('User-Agent')
        session.headers['User-Agent'] = BRAVE_USER_AGENT
        session.headers['Accept'] = 'application/json'
        session.headers['X-Subscription-Token'] = api_key
        js, code = get_json(session, url, tries=3, timeout=20)
        if code != 200 or not js:
            return []
        out = []
        for r in ((js.get('web') or {}).get('results') or [])[:limit]:
            out.append({
                'title': r.get('title') or 'Result',
                'url': r.get('url'),
                'description': (r.get('description') or '').strip(),
            })
        return [x for x in out if x.get('url')]
    except Exception:
        return []
    finally:
        # Clean up headers we set
        try:
            session.headers.pop('X-Subscription-Token', None)
            session.headers.pop('Accept', None)
            if old_ua:
                session.headers['User-Agent'] = old_ua
        except Exception:
            pass


def infer_why_line(it: dict, community_posts: list[dict], web_results: list[dict]):
    """Create a single 'why trending' line, preferring sourced explanations."""

    title = it.get('topic_title') or 'This'
    sent = (it.get('lead_sentence') or '').strip()

    # 1) Death heuristic: Wikipedia lead often switches to past tense.
    if re.search(r'\bwas an?\b', sent) and any(k in sent.lower() for k in [' was an ', ' was a ']):
        if any(k in sent.lower() for k in ['actor', 'actress', 'singer', 'politician', 'musician', 'model', 'athlete', 'businessman', 'journalist']):
            return {
                'line': f"{title}: likely spiking because news of their death is circulating.",
                'source': None,
                'confidence': 'medium',
            }

    # 2) If we have a strong community driver, use that headline as the reason.
    if community_posts:
        p = community_posts[0]
        headline = (p.get('title') or '').strip()
        if headline and len(headline) >= 12:
            return {
                'line': f"{title}: trending off the back of chatter/headlines like \"{headline}\".",
                'source': {'label': f"Reddit r/{p.get('subreddit','?')}", 'url': p.get('url')},
                'confidence': 'medium',
            }

    # 3) Prefer a web result from Brave (if available), because it’s usually 'the' news hook.
    if web_results:
        r = web_results[0]
        hook = (r.get('title') or r.get('description') or '').strip()
        hook = re.sub(r'\s+', ' ', hook)
        if hook:
            return {
                'line': f"{title}: likely connected to \"{hook}\".",
                'source': {'label': 'Web', 'url': r.get('url')},
                'confidence': 'medium',
            }

    # 4) Fallback: honest uncertainty.
    return {
        'line': f"{title}: unclear from this snapshot alone — likely a fresh headline or viral clip.",
        'source': None,
        'confidence': 'low',
    }


def main():
    BRIEFS_DIR.mkdir(exist_ok=True)

    run_date = _dt.date.today()
    # Allow backfills: set BRIEF_DATE=YYYY-MM-DD to force the brief date
    import os
    brief_date_env = os.environ.get('BRIEF_DATE')
    brief_date = _dt.date.fromisoformat(brief_date_env) if brief_date_env else (run_date - _dt.timedelta(days=1))

    out_path = BRIEFS_DIR / f'{brief_date.isoformat()}.md'
    if out_path.exists():
        print('ABORT: brief already exists')
        return 0

    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT

    # top list: brief_date
    top_day = brief_date
    top_json = None
    for back in range(0, 8):
        d = top_day - _dt.timedelta(days=back)
        url = f'https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{LANG}.{PROJECT}/{ACCESS}/{d.year:04d}/{d.month:02d}/{d.day:02d}'
        js, code = get_json(session, url)
        if code == 200:
            top_json = js
            top_list_date = d
            break
    if top_json is None:
        raise RuntimeError('No top list available')

    arts = top_json['items'][0]['articles']
    cand = [a for a in arts if is_normal(a.get('article', '')) and not a.get('article','').startswith('Wikipedia:')][:100]
    weights = [1.0 / max(1, int(a['rank'])) for a in cand]

    rng = random.Random(int(brief_date.strftime('%Y%m%d')))
    picks = weighted_sample_without_replacement(cand, weights, 10, rng)

    items = []
    domain_counts = {}
    for a in picks:
        title = a['article']
        rank = int(a['rank']); views = int(a['views'])
        url_sum = f'https://{LANG}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title, safe="")}'
        sumj, _ = get_json(session, url_sum)
        para = first_paragraph(sumj.get('extract'))
        sent = first_declarative(para)
        topic_url = ((sumj.get('content_urls', {}) or {}).get('desktop', {}) or {}).get('page')
        thumb = (sumj.get('thumbnail') or {}).get('source')
        items.append({
            'topic_title': sumj.get('title') or title.replace('_',' '),
            'rank': rank,
            'pageviews': views,
            'lead_sentence': sent,
            'description': (sumj.get('description') or '').strip(),
            'thumbnail_url': thumb,
            'topic_url': topic_url,
        })

    total_views = sum(i['pageviews'] for i in items)

    body = []
    items_by_views = sorted(items, key=lambda x: x['pageviews'], reverse=True)
    top3 = items_by_views[:3]

    # --- What’s trending ---
    body.append('## What’s trending (10 picks, quick read)\n')
    body.append(f"Total attention in this 10-pick snapshot: **~{total_views:,} pageviews**.\n\n")
    for it in items_by_views:
        body.append(f"- **{it['topic_title']}** — rank {it['rank']} · **{it['pageviews']:,}** views\n")

    # --- Why you’re seeing these ---
    # Enrichment policy:
    # - Always attempt external verification for top 3 by views
    # - For the rest: only if we have an obvious driver (community post) or Brave API key is available
    # - Keep it small + throttled
    why_blocks = []
    external_sources = []

    body.append('\n\n## Why you’re seeing these (best guess)\n')

    for idx, it in enumerate(items_by_views):
        # Community driver: small reddit search (often catches the "what happened" headline)
        comm = []
        if idx < 3 or (it.get('topic_title') and len(it['topic_title']) >= 3):
            comm = search_community_sources(session, it['topic_title'], limit=1)
            time.sleep(1.0)

        # Web driver: Brave search if configured; only for top3 or if we didn't get a comm headline
        web = []
        if idx < 3 or (not comm):
            web = brave_web_search(session, f"{it['topic_title']} why trending", limit=1)
            if web:
                time.sleep(1.0)

        why = infer_why_line(it, comm, web)
        line = why['line']
        src = why.get('source')

        if src and src.get('url'):
            label = src.get('label') or 'Source'
            body.append(f"- **{it['topic_title']}:** {line.split(':',1)[1].strip()} ([{label}]({src['url']}))\n")
            external_sources.append({'title': it['topic_title'], 'label': label, 'url': src['url']})
        else:
            body.append(f"- **{it['topic_title']}:** {line.split(':',1)[1].strip()}\n")

    # --- Quick context ---
    body.append('\n\n## Quick context\n')
    for it in items_by_views:
        desc = (it.get('description') or '').strip()
        if desc:
            body.append(f"- **{it['topic_title']}** — {desc}.\n")
        else:
            body.append(f"- **{it['topic_title']}** — {it.get('lead_sentence','').strip()}\n")

    body.append('\n## Receipts\n')
    body.append('**Wikipedia (top drivers):**\n')
    for it in top3:
        if it.get('topic_url'):
            body.append(f"- [{it['topic_title']}]({it['topic_url']})\n")

    # External sources used to justify specific 'why trending' claims
    if external_sources:
        body.append('\n**Additional sources:**\n')
        seen = set()
        for s in external_sources:
            u = s.get('url')
            if not u or u in seen:
                continue
            seen.add(u)
            label = s.get('label') or 'Source'
            t = s.get('title') or 'Link'
            body.append(f"- [{t} — {label}]({u})\n")

    body.append('\n## The 10 Picks\n')
    body.append('<div class="grid">')
    for it in sorted(items, key=lambda x: x['pageviews'], reverse=True):
        img = f"<img src=\"{it['thumbnail_url']}\" alt=\"\" loading=\"lazy\" />" if it.get('thumbnail_url') else ''
        body.append('\n'.join([
            '<div class="card">',
            f"  <div class=\"kicker\">Rank {it['rank']} · {it['pageviews']} views</div>",
            f"  <div class=\"card__title\">{it['topic_title']}</div>",
            f"  <div class=\"thumb\">{img}</div>" if img else '',
            f"  <div class=\"quote\">{it['lead_sentence']}</div>",
            f"  <div class=\"muted small\"><a href=\"{it['topic_url']}\" target=\"_blank\" rel=\"noopener\">Wikipedia</a></div>",
            '</div>'
        ]))
    body.append('</div>')

    front = [
        '---',
        'layout: "brief"',
        f'title: {yq(f"Today’s Trend Brief ({brief_date.isoformat()})")}',
        f'brief_date: {yq(brief_date.isoformat())}',
        f'top_list_date: {yq(top_list_date.isoformat())}',
        f'total_pageviews: {total_views}',
        'summary: "A tight, daily snapshot of what’s drawing collective attention — and why."',
        '---',
        ''
    ]

    out_path.write_text('\n'.join(front) + '\n'.join(body) + '\n', encoding='utf-8')
    print('OK', out_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
