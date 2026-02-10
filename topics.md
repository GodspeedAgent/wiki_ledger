---
layout: default
title: Topics
---

<section class="hero">
  <h1 class="hero__title">Topics</h1>
  <p class="hero__subtitle">Each topic page aggregates every time it appeared, and highlights sentence differences when the lead sentence changes.</p>
</section>

<section class="stack">
  {% assign topics_sorted = site.topics | sort: 'times_seen_total' | reverse %}
  {% for t in topics_sorted %}
    <a class="card card--link" href="{{ t.url | relative_url }}">
      <div class="card__row">
        <div>
          <div class="kicker">Seen {{ t.times_seen_total }} time(s) · Sentence changes {{ t.sentence_changed_count }}</div>
          <div class="card__title">{{ t.topic_title }}</div>
        </div>
      </div>
    </a>
  {% endfor %}
</section>
