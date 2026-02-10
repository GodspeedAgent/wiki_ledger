---
layout: default
title: Brief archive
---

<section class="hero">
  <h1 class="hero__title">Brief archive</h1>
  <p class="hero__subtitle">Past daily briefs (kept for reference; the Brief tab always points to the latest).</p>
</section>

<section class="stack">
  {% assign briefs_sorted = site.briefs | sort: 'brief_date' | reverse %}
  {% if briefs_sorted.size == 0 %}
    <div class="card muted">No briefs yet.</div>
  {% endif %}
  {% for b in briefs_sorted %}
    <a class="card card--link" href="{{ b.url | relative_url }}">
      <div class="kicker">{{ b.brief_date }}</div>
      <div class="card__title">{{ b.title }}</div>
      {% if b.summary %}<div class="quote">{{ b.summary }}</div>{% endif %}
    </a>
  {% endfor %}
</section>
