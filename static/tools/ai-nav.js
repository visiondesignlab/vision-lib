const {path} = window.VisionSite;
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const favoritesKey = 'vision.ai-navigation.favorites:' + path('/');
function favorites(aliases){
  try {
    const ids=JSON.parse(localStorage.getItem(favoritesKey) || '[]');
    if(!Array.isArray(ids))return [];
    const clean=[...new Set(ids.filter(x=>typeof x==='string').map(id=>aliases.get(id) || id))];
    if(ids.some(id=>aliases.has(id))){
      try{localStorage.setItem(favoritesKey,JSON.stringify(clean));}catch{}
    }
    return clean;
  } catch { return []; }
}
window.addEventListener('storage',event=>{
  if(event.key===favoritesKey || event.key===null) document.querySelector('.ai-directory')?.dispatchEvent(new Event('favoriteschange'));
});
const host = url => { try{return new URL(url).hostname.replace(/^www\./, '');}catch{return '';} };
const searchText = s => s.toLowerCase().replace(/\s+/g, '');

function iconHTML(icon) {
  const bundled = /^\/static\/tools\/ai-icons\/([a-f0-9]{20})\.webp$/.exec(icon || '');
  if (bundled) return `<span class="ai-icon" aria-hidden="true" data-asset="${bundled[1]}"></span>`;
  return icon ? `<span class="ai-icon" aria-hidden="true"><img loading="lazy" alt="" src="${esc(path(icon))}"></span>` : '';
}

function rankingPreview(entry) {
  const ranking = entry.ranking;
  if (!ranking?.rows?.length) return '';
  const rows = ranking.rows.map((row, index) => `<tr><td>${index + 1}</td><th scope="row"><a href="${esc(row.url)}" target="_blank" rel="noopener noreferrer">${esc(row.model)}</a></th><td>${esc(row.provider)}</td><td>${esc(row.score)}</td></tr>`).join('');
  return `<div class="ai-ranking"><div class="ai-ranking-head"><h3>智能指数前 ${ranking.rows.length} 名</h3><time datetime="${esc(ranking.date)}">${esc(ranking.date)} 快照</time></div>
    <table aria-label="Artificial Analysis 智能指数排名"><thead><tr><th scope="col">排名</th><th scope="col">模型</th><th scope="col">开发商</th><th scope="col">智能指数</th></tr></thead><tbody>${rows}</tbody></table>
    <a class="ai-ranking-source" href="${esc(entry.url)}" target="_blank" rel="noopener noreferrer">查看 Artificial Analysis 完整榜单 ↗</a></div>`;
}

export function directory({categories, entries}, replaceURL, enhanceSelect) {
  const aliases = new Map(entries.flatMap(row=>(row.previousIds || []).map(id=>[id,row.id])));
  const el = document.createElement('section');
  el.className = 'ai-directory';
  const params = new URL(location.href).searchParams;
  let category = categories.some(c => c.id === params.get('category')) ? params.get('category') : '';
  const filters = [{id:'', name:'全部分类'}, ...categories];
  el.innerHTML = `<header class="ai-directory-head"><h1>AI 导航</h1><span>${categories.length} 个分类 · ${entries.length} 个入口</span></header>
    <div class="ai-layout"><aside class="ai-categories" aria-label="入口分类"></aside><div class="ai-results">
    <div class="ai-filters"><div class="ai-mobile-category"><select id="ai-directory-category" aria-label="选择分类">${filters.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select></div>
    <input type="search" aria-label="搜索 AI 入口" placeholder="搜索名称、用途或网址"></div>
    <div class="ai-summary" role="status"></div><div class="ai-groups"></div></div></div>
`;
  const $ = s => el.querySelector(s);
  const q = $('input'), select = $('select'), rail = $('.ai-categories');
  const syncCategoryLabel = enhanceSelect(select, '选择分类');
  q.value = params.get('q') || '';
  rail.innerHTML = filters.map(c => `<button type="button" data-category="${esc(c.id)}">${esc(c.name)}</button>`).join('');
  function card(x, saved){
    const checked=saved.has(x.id);
    return `<div class="ai-card"><a class="ai-link" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${iconHTML(x.icon)}<span class="ai-link-text"><strong>${esc(x.name)}</strong><span>${esc(x.description || host(x.url))}</span></span></a><button type="button" class="ai-favorite" data-favorite="${esc(x.id)}" aria-label="${checked?'取消收藏':'收藏'}：${esc(x.name)}" aria-pressed="${checked}" title="${checked?'取消收藏':'收藏'}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.8 5.7 6.3.9-4.5 4.5 1 6.3L12 17.5l-5.6 2.9 1-6.3-4.5-4.5 6.3-.9Z"/></svg></button></div>`;
  }
  function render(syncURL) {
    const term = searchText(q.value.trim());
    if (syncURL) {
      const url = new URL(location.href);
      for (const [k, v] of [['category', category], ['q', q.value.trim()]]) {
        if (v) url.searchParams.set(k, v); else url.searchParams.delete(k);
      }
      replaceURL(url);
    }
    select.value = category; syncCategoryLabel();
    for (const b of rail.children) b.setAttribute('aria-pressed', String(b.dataset.category === category));
    const ids=favorites(aliases), saved=new Set(ids), shown=new Map(), sections=[];
    function group(key,name,rows){
      const ranking = rows.find(row => row.category === key && row.ranking);
      return rows.length?`<section data-section="${esc(key)}"><h2>${esc(name)} <small>${rows.length}</small></h2>${ranking ? rankingPreview(ranking) : ''}<div class="ai-links">${rows.map(x=>card(x,saved)).join('')}</div></section>`:'';
    }
    for (const c of categories) {
      if (category && c.id !== category) continue;
      const rows = entries.filter(x => x.category === c.id && (!term || searchText([x.name, x.url, x.description, c.name, ...(x.aliases || []), ...(x.ranking?.rows || []).map(row => row.model + ' ' + row.provider)].join(' ')).includes(term)));
      for(const x of rows)shown.set(x.id,x);
      if(rows.length)sections.push(group(c.id,c.name,rows));
    }
    const top = group('featured','推荐',[...shown.values()].filter(x=>x.featured)) +
      group('favorites','我的收藏',ids.map(id=>shown.get(id)).filter(Boolean));
    const count = shown.size;
    $('.ai-summary').textContent = term ? `找到 ${count} 个入口` : '';
    $('.ai-groups').innerHTML = (top + sections.join('')) || '<div class="empty"><b>没有匹配的入口</b><p>试试其他关键词或分类。</p><button type="button" class="pill-btn shadow">查看全部入口</button></div>';
    $('.empty button')?.addEventListener('click', () => { category = ''; q.value = ''; render(true); });
  }
  el.addEventListener('error', e => { if (e.target.matches('.ai-icon img')) e.target.remove(); }, true);
  el.addEventListener('favoriteschange',()=>render(false));
  el.addEventListener('click',e=>{
    const b=e.target.closest('[data-favorite]');if(!b)return;
    const id=b.dataset.favorite, section=b.closest('[data-section]').dataset.section, ids=favorites(aliases);
    const next=ids.includes(id)?ids.filter(x=>x!==id):[id,...ids];
    try{localStorage.setItem(favoritesKey,JSON.stringify(next));}
    catch{$('.ai-summary').textContent='当前浏览器无法保存收藏。';return;}
    render(false);
    const selector=`[data-favorite="${CSS.escape(id)}"]`;
    (el.querySelector(`[data-section="${CSS.escape(section)}"] ${selector}`) || el.querySelector(selector))?.focus({preventScroll:true});
  });
  rail.onclick = e => { const b = e.target.closest('button'); if (b) { category = b.dataset.category; render(true); window.scrollTo(0, 0); } };
  select.onchange = () => { category = select.value; render(true); };
  q.oninput = () => render(true);
  render(false);
  return el;
}
