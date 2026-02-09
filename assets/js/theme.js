(function(){
  const storageKey = 'wikiledger-theme';
  const root = document.documentElement;

  function getPreferred(){
    const saved = localStorage.getItem(storageKey);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function apply(theme){
    root.dataset.theme = theme;
  }

  apply(getPreferred());

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    const next = (root.dataset.theme === 'dark') ? 'light' : 'dark';
    localStorage.setItem(storageKey, next);
    apply(next);
  });
})();
