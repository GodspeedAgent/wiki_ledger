(function(){
  // Simple client-side filter/search for the Daily page.
  const root = document.documentElement;
  const pageKind = root.dataset.pageKind;
  if (pageKind !== 'daily') return;

  const q = document.querySelector('[data-filter-q]');
  const selDomain = document.querySelector('[data-filter-domain]');
  const selEntity = document.querySelector('[data-filter-entity]');
  const chips = Array.from(document.querySelectorAll('[data-filter-chip]'));
  const cards = Array.from(document.querySelectorAll('[data-entry-card]'));
  const counter = document.querySelector('[data-filter-count]');

  function norm(s){
    return (s || '').toString().toLowerCase().trim();
  }

  function apply(){
    const query = norm(q && q.value);
    const domain = norm(selDomain && selDomain.value);
    const entity = norm(selEntity && selEntity.value);
    const activeChip = norm((chips.find(c => c.classList.contains('chip--on')) || {}).dataset.filterChip);

    let shown = 0;
    cards.forEach(card => {
      const t = norm(card.dataset.title);
      const s = norm(card.dataset.sentence);
      const d = norm(card.dataset.domain);
      const e = norm(card.dataset.entity);

      const matchQ = !query || t.includes(query) || s.includes(query);
      const matchD = !domain || d === domain;
      const matchE = !entity || e === entity;

      // chip is a shortcut
      const matchChip = !activeChip || (activeChip === 'changed' ? card.dataset.changed === 'true' : true);

      const ok = matchQ && matchD && matchE && matchChip;
      card.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });

    if (counter) counter.textContent = shown.toString();
  }

  function toggleChip(chip){
    chips.forEach(c => c.classList.remove('chip--on'));
    if (!chip.classList.contains('chip--on')) chip.classList.add('chip--on');
  }

  if (q) q.addEventListener('input', apply);
  if (selDomain) selDomain.addEventListener('change', apply);
  if (selEntity) selEntity.addEventListener('change', apply);
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const wasOn = chip.classList.contains('chip--on');
      chips.forEach(c => c.classList.remove('chip--on'));
      if (!wasOn) chip.classList.add('chip--on');
      apply();
    });
  });

  apply();
})();
