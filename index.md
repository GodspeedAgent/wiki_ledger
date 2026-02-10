---
layout: default
title: Daily log
page_kind: daily
---

<section class="hero">
  <h1 class="hero__title">Daily tracker</h1>
  <p class="hero__subtitle">A searchable, filterable log of the most-read Wikipedia lead sentence, one day at a time.</p>
</section>

<section class="card filters">
  <div class="filters__row">
    <label class="filters__field">
      <span class="filters__label">Search</span>
      <input class="input" type="search" placeholder="Try: Epstein, football, film…" data-filter-q />
    </label>

    <label class="filters__field">
      <span class="filters__label">Domain</span>
      <select class="select" data-filter-domain>
        <option value="">All</option>
        <option value="news">News</option>
        <option value="politics">Politics</option>
        <option value="crime">Crime</option>
        <option value="sports">Sports</option>
        <option value="entertainment">Entertainment</option>
        <option value="tech">Tech</option>
        <option value="history">History</option>
        <option value="science">Science</option>
        <option value="other">Other</option>
      </select>
    </label>

    <label class="filters__field">
      <span class="filters__label">Entity</span>
      <select class="select" data-filter-entity>
        <option value="">All</option>
        <option value="person">Person</option>
        <option value="place">Place</option>
        <option value="event">Event</option>
        <option value="work">Work</option>
        <option value="org">Org</option>
        <option value="other">Other</option>
      </select>
    </label>

    <div class="filters__meta">
      <div class="kicker">Showing <span data-filter-count>0</span> entries</div>
      <div class="chips">
        <button class="chip" type="button" data-filter-chip="changed">Changed</button>
      </div>
    </div>
  </div>
</section>

<section class="stack">
  {% assign entries_sorted = site.entries | sort: 'date' | reverse %}
  {% if entries_sorted.size == 0 %}
    <div class="card muted">No entries yet.</div>
  {% endif %}

  {% for e in entries_sorted %}
    <a
      class="card card--link"
      href="{{ e.url | relative_url }}"
      data-entry-card
      data-title="{{ e.topic_title | escape }}"
      data-sentence="{{ e.lead_sentence | escape }}"
      data-domain="{{ e.domain | default: 'other' | downcase }}"
      data-entity="{{ e.entity_type | default: 'other' | downcase }}"
      data-changed="{% if e.sentence_changed %}true{% else %}false{% endif %}"
    >
      <div class="card__row">
        <div>
          <div class="kicker">{{ e.date | date: '%Y-%m-%d' }} · Rank {{ e.rank }} · {{ e.pageviews }} views</div>
          <div class="card__title">{{ e.topic_title }}</div>
          <div class="kicker">{% if e.domain %}{{ e.domain }}{% endif %}{% if e.domain and e.entity_type %} · {% endif %}{% if e.entity_type %}{{ e.entity_type }}{% endif %}</div>
        </div>
        <div class="pill {% if e.sentence_changed %}pill--hot{% else %}pill--cool{% endif %}">
          {% if e.sentence_changed %}Changed{% else %}Same{% endif %}
        </div>
      </div>
      <div class="quote">{{ e.lead_sentence }}</div>
    </a>
  {% endfor %}
</section>
