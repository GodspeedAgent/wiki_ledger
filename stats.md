---
layout: default
title: Stats
---

<section class="hero">
  <h1 class="hero__title">Stats</h1>
  <p class="hero__subtitle">High-level counters for the log.</p>
</section>

<section class="grid">
  <div class="card">
    <div class="card__title">Total days logged</div>
    <div class="big">{{ site.entries | size }}</div>
  </div>

  <div class="card">
    <div class="card__title">Unique topics</div>
    <div class="big">
      {% assign titles = site.entries | map: 'topic_title' | uniq %}
      {{ titles | size }}
    </div>
  </div>

  <div class="card">
    <div class="card__title">Days with sentence changes</div>
    <div class="big">
      {% assign changed = site.entries | where: 'sentence_changed', true %}
      {{ changed | size }}
    </div>
  </div>
</section>
