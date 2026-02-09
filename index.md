---
layout: default
title: Daily log
---

<section class="hero">
  <h1 class="hero__title">Daily tracker</h1>
  <p class="hero__subtitle">A simple, card-based log of the most-read Wikipedia lead sentence, one day at a time.</p>
</section>

<section class="stack">
  {% assign entries_sorted = site.entries | sort: 'date' | reverse %}
  {% if entries_sorted.size == 0 %}
    <div class="card muted">No entries yet.</div>
  {% endif %}

  {% for e in entries_sorted %}
    <a class="card card--link" href="{{ e.url | relative_url }}">
      <div class="card__row">
        <div>
          <div class="kicker">{{ e.date | date: '%Y-%m-%d' }} · Rank {{ e.rank }} · {{ e.pageviews }} views</div>
          <div class="card__title">{{ e.topic_title }}</div>
        </div>
        <div class="pill {% if e.sentence_changed %}pill--hot{% else %}pill--cool{% endif %}">
          {% if e.sentence_changed %}Changed{% else %}Same{% endif %}
        </div>
      </div>
      <div class="quote">{{ e.lead_sentence }}</div>
    </a>
  {% endfor %}
</section>
