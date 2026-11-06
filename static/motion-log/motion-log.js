const {path: sitePath, icon} = window.VisionSite;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link = id => sitePath('/motion-log' + (id ? '?id=' + encodeURIComponent(id) : ''));
const asset = (id, file) => sitePath('/static/motion-log/' + id + '/' + file);
let catalog;
async function loadCatalog() {
  return catalog ||= fetch(sitePath('/static/motion-log/index.json')).then(r => {
    if (!r.ok) throw new Error('无法读取日志');
    return r.json();
  }).catch(error => {catalog = null; throw error;});
}
const outside = (url, label) => `<a class="pill-btn shadow" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label} ${icon('external')}</a>`;
function card(item) {
  return `<a data-link class="motion-card" href="${link(item.id)}">
    <div class="motion-cover">${item.cover ? `<img src="${esc(item.cover)}" alt="${esc(item.title)}" loading="lazy" referrerpolicy="no-referrer">` : ''}<span class="motion-duration">${esc(item.duration)}</span></div>
    <div class="motion-card-meta"><time datetime="${item.date}">${item.date.replaceAll('-','.')}</time><span>${esc(item.brand)}</span></div>
    <h2>${esc(item.title)}</h2><p>${esc(item.intro)}</p>
    <span class="motion-read">阅读报告 ${icon('forward')}</span></a>`;
}

export async function renderMotionLog(view, id, signal) {
  const list = await loadCatalog();
  if (signal.aborted || !view.isConnected) return;
  if (!id) {
    view.innerHTML = `<header class="head"><h1>拉片日志</h1><span class="sub">${list.length} 篇单片报告 · 镜头、叙事与声音</span></header><div class="motion-grid">${list.map(card).join('')}</div>`;
    hideBrokenCovers(view);
    return;
  }
  const item = list.find(x => x.id === id);
  const back = `<a class="pill-btn grey" data-link href="${link()}">${icon('back')} 拉片日志</a>`;
  if (!item) {view.innerHTML = back + '<p class="empty">未收录这篇报告。</p>'; return;}
  const response = await fetch(asset(id, 'report.html'), {signal});
  if (!response.ok) throw new Error('报告暂时无法读取');
  const html = await response.text();
  if (signal.aborted || !view.isConnected) return;
  document.title = item.title + ' · 拉片日志 · Vision Lab';
  view.innerHTML = `<div class="motion-toolbar">${back}<div>${outside(item.sourcePage, '查看原片')}${outside(item.reportSource, '原始报告')}</div></div>
    <header class="motion-heading"><div class="motion-card-meta"><time>${item.date.replaceAll('-','.')}</time><span>拉片日志</span></div><h1>${esc(item.title)}</h1><p>${esc(item.creator)} · ${esc(item.duration)}</p></header>
    <div class="motion-layout"><div class="motion-main">
      <section class="motion-player" id="motion-player" aria-label="原片播放器">
        <iframe src="${esc(item.embed)}" title="${esc(item.title)} 原片" allow="autoplay; fullscreen; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>
      </section>
      <p class="motion-player-note">原站嵌入播放。若播放器不可用，可<a href="${esc(item.sourcePage)}" target="_blank" rel="noopener noreferrer">查看原片 ${icon('external')}</a>。</p>
      ${item.missingAttachments ? '<p class="motion-source-note">完整报告正文已保留。源文件夹未归档关键帧图片与分析附件，下文保留对应说明和时间码。</p>' : ''}
      <article class="motion-report">${html}</article>
      <footer class="motion-report-footer"><a class="pill-btn shadow" href="${asset(id,'report.md')}" download>下载报告 Markdown</a>${back}</footer>
    </div><aside class="motion-toc" aria-label="报告目录"><b>报告目录</b><a href="#motion-player">原片</a>${item.toc.map(h=>`<a href="#${esc(h.id)}">${esc(h.title)}</a>`).join('')}</aside></div>`;
  const frame = view.querySelector('iframe');
  signal.addEventListener('abort', () => frame.remove(), {once:true});
  mountReportNavigation(view, signal);
}

function mountReportNavigation(view, signal) {
  const player = view.querySelector('.motion-player');
  const links = [...view.querySelectorAll('.motion-toc a')];
  const sections = links.map(a => view.querySelector(a.getAttribute('href')));
  let scheduled = 0, anchorOffset = 24;
  const stickyTop = () => parseFloat(getComputedStyle(player).top) || 0;
  function activate(id) {
    for (const a of links) {
      const active = a.getAttribute('href') === '#' + id;
      a.classList.toggle('is-active', active);
      if (active) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    }
  }
  function update() {
    scheduled = 0;
    if (signal.aborted || !view.isConnected) return;
    const readingLine = player.getBoundingClientRect().bottom + 32;
    let current = sections[0];
    for (const section of sections.slice(1)) {
      if (section.getBoundingClientRect().top <= readingLine) current = section;
      else break;
    }
    if (scrollY > 0 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2) current = sections.at(-1);
    activate(current.id);
  }
  function schedule() {if (!scheduled) scheduled = requestAnimationFrame(update);}
  function measure() {
    anchorOffset = stickyTop() + player.getBoundingClientRect().height + 24;
    view.style.setProperty('--motion-anchor-offset', anchorOffset + 'px');
    schedule();
  }
  const observer = new ResizeObserver(measure);
  observer.observe(player);
  window.addEventListener('scroll', schedule, {passive:true, signal});
  window.addEventListener('resize', measure, {passive:true, signal});
  signal.addEventListener('abort', () => {observer.disconnect(); cancelAnimationFrame(scheduled);}, {once:true});
  view.addEventListener('click', event => {
    const a = event.target.closest('a[href^="#"]');
    if (!a) return;
    const target = view.querySelector(a.getAttribute('href'));
    if (!target) return;
    event.preventDefault();
    measure();
    if (target === player) {
      // The sticky player's viewport position no longer represents its original location.
      const main = view.querySelector('.motion-main');
      window.scrollTo({top:scrollY + main.getBoundingClientRect().top - stickyTop(), behavior:'instant'});
    } else window.scrollTo({top:scrollY + target.getBoundingClientRect().top - anchorOffset, behavior:'instant'});
    activate(target.id);
  }, {signal});
  measure();
}

function hideBrokenCovers(view) {
  for (const img of view.querySelectorAll('.motion-cover img')) {
    img.addEventListener('error', () => {img.hidden = true;}, {once:true});
  }
}
