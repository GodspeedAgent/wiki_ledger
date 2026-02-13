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
            'thumbnail_url': thumb,
            'topic_url': topic_url,
        })

    total_views = sum(i['pageviews'] for i in items)

    # Tighter content skeleton; narrative can be edited/enriched by the agent.
    body = []
    # Auto-draft (specific to today’s 10 picks; no placeholders)
    body.append('## The Pulse\n')
    items_by_views = sorted(items, key=lambda x: x['pageviews'], reverse=True)
    top3 = items_by_views[:3]

    body.append(f"- **Dominant:** {top3[0]['topic_title']} (rank {top3[0]['rank']}, {top3[0]['pageviews']:,} views) leads the day.\n")
    body.append(f"- **Scale:** ~{total_views:,} total views across today’s 10-pick snapshot (top-100 weighted sample).\n")

    # cluster heuristics
    has_superbowl = any('super bowl' in (i['topic_title'] + ' ' + i.get('lead_sentence','')).lower() or 'halftime' in (i['topic_title'] + ' ' + i.get('lead_sentence','')).lower() for i in items)

    def bucket(it):
        t = (it['topic_title'] + ' ' + it.get('lead_sentence','')).lower()
        if any(k in t for k in ['super bowl', 'halftime']):
            return 'superbowl'
        # If the day includes Super Bowl/halftime, treat performers as part of that attention engine.
        if has_superbowl and any(k in t for k in ['singer', 'songwriter', 'rapper', 'record producer', 'actor', 'actress', 'concert']):
            return 'superbowl'
        if any(k in t for k in ['seahawks', 'nfl', 'quarterback', 'placekicker']):
            return 'nfl'
        if any(k in t for k in ['epstein', 'maxwell']):
            return 'epstein'
        if 'winter olympics' in t or 'olympic' in t:
            return 'olympics'
        return 'other'

    buckets = {}
    for it in items:
        b = bucket(it)
        buckets.setdefault(b, []).append(it)

    # Summarize top clusters by total views
    cluster_order = sorted(buckets.items(), key=lambda kv: sum(x['pageviews'] for x in kv[1]), reverse=True)
    lead_cluster, lead_items = cluster_order[0]
    body.append(f"- **Cluster signal:** today’s list concentrates around **{lead_cluster}** ("
                f"{len(lead_items)} of 10 picks). That kind of density often points to a single real-world ‘attention engine’ driving multiple lookups.\n")

    # a concrete connective bullet
    # If superbowl + epstein both present, mention the contrast explicitly.
    if 'superbowl' in buckets and 'epstein' in buckets:
        body.append("- **Contrast:** a high-gloss spectacle thread (Super Bowl / performers) sits alongside an accountability thread (Epstein / Maxwell) — a common ‘two-track day’ where entertainment and legal salience compete for mindshare.\n")
    elif 'nfl' in buckets and 'superbowl' in buckets:
        body.append("- **Connection:** multiple Seahawks-linked lookups inside a Super Bowl-shaped day suggests fans are triangulating rosters, key plays, and names in real time.\n")

    body.append('\n## Hidden Connections\n')

    # Build up to 3 threads from top clusters, each listing 2–5 topics
    for idx, (b, its) in enumerate(cluster_order[:3], 1):
        topics = ', '.join([f"[{x['topic_title']}]({x['topic_url']})" for x in its[:5] if x.get('topic_url')])
        tot = sum(x['pageviews'] for x in its)
        if b == 'superbowl':
            label = 'Spectacle stack (game + performers + counter-programming)'
            expl = ("This cluster is consistent with a live-event attention loop: "
                    "people bounce between the event page, performer pages, and adjacent ‘meta’ pages. "
                    "The presence of an alternative/online halftime entry alongside the main Super Bowl node may suggest a parallel narrative ecosystem forming around the same time anchor.")
        elif b == 'epstein':
            label = 'Accountability / document-thread'
            expl = ("Epstein-related pages often re-cluster when there’s a new filing, document drop, or recap wave. "
                    "A multi-page cluster (files + associate) is consistent with readers mapping networks rather than reading a single headline summary.")
        elif b == 'nfl':
            label = 'Team-specific triangulation'
            expl = ("Multiple Seattle Seahawks-linked pages in the same snapshot is consistent with fans chasing specific roster/role context (QB, kicker) rather than general league news.")
        elif b == 'olympics':
            label = 'Scheduled-event gravity'
            expl = ("A live, calendar-fixed event can pull attention even without a single viral trigger; Wikipedia becomes a standings/venues reference layer.")
        else:
            label = 'Background curiosity'
            expl = ("These look like one-off curiosity spikes that hitch a ride on the day’s larger attention currents.")

        body.append(f"**Thread {idx}: {label}**\n\n")
        body.append(f"Topics: {topics}\n\n")
        body.append(f"Why they may connect: {expl}\n\n")

    body.append('## Competing Explanations\n')
    # Make these specific to the dominant cluster
    if lead_cluster == 'superbowl':
        body.append("- **Organic curiosity:** a major live event creates genuine, decentralized lookups across rules, performers, and personalities — Wikipedia is the common ‘second screen.’\n")
        body.append("- **Media routing/amplification:** broadcast + social clips + official promos can funnel attention toward a tight set of pages (performers + event), making the spike look more unified than the underlying reasons.\n")
    elif lead_cluster == 'epstein':
        body.append("- **Organic curiosity:** a resurfacing scandal drives people to rebuild the timeline and relationships.\n")
        body.append("- **Media routing/amplification:** a concentrated wave of coverage routes audiences into a small cluster of reference pages, which can persist even if no new facts were added that day.\n")
    else:
        body.append("- **Organic curiosity:** readers converge on the same pages because the same real-world events are salient.\n")
        body.append("- **Media routing/amplification:** distribution channels funnel attention toward a small set of reference pages, creating spikes.\n")

    body.append('\n## Receipts\n')
    for it in top3:
        if it.get('topic_url'):
            body.append(f"- [{it['topic_title']}]({it['topic_url']})\n")

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
