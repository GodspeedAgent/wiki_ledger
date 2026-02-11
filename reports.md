---
layout: default
title: Reports (deprecated)
---

<section class="hero">
  <h1 class="hero__title">Reports</h1>
  <p class="hero__subtitle">Weekly and monthly insight briefs generated from the daily log (with supporting links when available).</p>
</section>

<section class="stack">
  <h2 class="h2">Weekly</h2>
  {% assign weekly = site.reports | where: 'report_kind', 'weekly' | sort: 'period_start' | reverse %}
  {% if weekly.size == 0 %}<div class="card muted">No weekly reports yet.</div>{% endif %}
  {% for r in weekly %}
    <a class="card card--link" href="{{ r.url | relative_url }}">
      <div class="card__row">
        <div>
          <div class="kicker">Week of {{ r.period_start }}</div>
          <div class="card__title">{{ r.title }}</div>
        </div>
      </div>
      {% if r.summary %}<div class="quote">{{ r.summary }}</div>{% endif %}
    </a>
  {% endfor %}
</section>

<section class="stack">
  <h2 class="h2">Monthly</h2>
  {% assign monthly = site.reports | where: 'report_kind', 'monthly' | sort: 'period_start' | reverse %}
  {% if monthly.size == 0 %}<div class="card muted">No monthly reports yet.</div>{% endif %}
  {% for r in monthly %}
    <a class="card card--link" href="{{ r.url | relative_url }}">
      <div class="card__row">
        <div>
          <div class="kicker">{{ r.period_start | slice: 0, 7 }}</div>
          <div class="card__title">{{ r.title }}</div>
        </div>
      </div>
      {% if r.summary %}<div class="quote">{{ r.summary }}</div>{% endif %}
    </a>
  {% endfor %}
</section>
