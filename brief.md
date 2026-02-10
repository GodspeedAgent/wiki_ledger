---
layout: default
title: Today’s Trend Brief
---

<section class="hero">
  <h1 class="hero__title">Today’s Trend Brief</h1>
  <p class="hero__subtitle">A tight, daily snapshot of what’s drawing collective attention — with connections and competing explanations.</p>
</section>

{% assign briefs_sorted = site.briefs | sort: 'brief_date' | reverse %}
{% assign latest = briefs_sorted | first %}

{% if latest %}
  <section class="card">
    <div class="kicker">Latest brief</div>
    <div class="card__title">{{ latest.title }}</div>
    {% if latest.summary %}<div class="quote">{{ latest.summary }}</div>{% endif %}
    <div style="margin-top:12px;">
      <a class="btn btn--ghost" href="{{ latest.url | relative_url }}">Read today’s brief</a>
    </div>
    <div class="muted small" style="margin-top:10px;">
      Archive: <a href="{{ '/briefs' | relative_url }}">all briefs</a>
    </div>
  </section>
{% else %}
  <section class="card muted">No brief yet. It will appear after the next daily run.</section>
{% endif %}
