// Lightweight word-diff for topic pages.
// No dependencies, no build step.
(function(){
  if (document.documentElement.dataset.pageKind !== 'topic') return;

  const nodes = Array.from(document.querySelectorAll('[data-diff-target]'));
  if (nodes.length < 2) return;

  function tokenize(s){
    return s.split(/(\s+|[\.,;:!?()\[\]"“”'’—–-])/).filter(t => t && t.length);
  }

  // LCS-based diff at token level.
  function diffTokens(aTokens, bTokens){
    const n=aTokens.length, m=bTokens.length;
    const dp = Array.from({length:n+1}, ()=> new Array(m+1).fill(0));
    for (let i=1;i<=n;i++){
      for (let j=1;j<=m;j++){
        dp[i][j] = aTokens[i-1]===bTokens[j-1] ? dp[i-1][j-1]+1 : Math.max(dp[i-1][j], dp[i][j-1]);
      }
    }
    const out=[];
    let i=n, j=m;
    while(i>0 && j>0){
      if (aTokens[i-1]===bTokens[j-1]){ out.push({t:aTokens[i-1], op:'='}); i--; j--; }
      else if (dp[i-1][j] >= dp[i][j-1]){ out.push({t:aTokens[i-1], op:'-'}); i--; }
      else { out.push({t:bTokens[j-1], op:'+'}); j--; }
    }
    while(i>0){ out.push({t:aTokens[i-1], op:'-'}); i--; }
    while(j>0){ out.push({t:bTokens[j-1], op:'+'}); j--; }
    out.reverse();
    return out;
  }

  function render(diff){
    const frag = document.createDocumentFragment();
    diff.forEach(part => {
      if (part.op === '=') frag.appendChild(document.createTextNode(part.t));
      else if (part.op === '+'){
        const ins=document.createElement('ins');
        ins.className='diff-ins';
        ins.textContent=part.t;
        frag.appendChild(ins);
      } else {
        const del=document.createElement('del');
        del.className='diff-del';
        del.textContent=part.t;
        frag.appendChild(del);
      }
    });
    return frag;
  }

  // Compare each sentence to the previous one and annotate the current.
  for (let k=1;k<nodes.length;k++){
    const prev = nodes[k-1].textContent.trim();
    const curr = nodes[k].textContent.trim();
    const d = diffTokens(tokenize(prev), tokenize(curr));
    nodes[k].textContent='';
    nodes[k].appendChild(render(d));
  }
})();
