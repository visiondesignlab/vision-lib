import {mountFrameViewer} from './frame-viewer.js';

const {path: sitePath, icon} = window.VisionSite;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link = id => sitePath('/motion-log' + (id ? '?id=' + encodeURIComponent(id) : ''));
const asset = (id, file) => sitePath('/static/motion-log/' + id + '/' + file);
function autoplayEmbed(embed) {
  const url = new URL(embed);
  url.searchParams.set('autoplay', '1');
  url.searchParams.set('muted', '0');
  url.searchParams.set('playsinline', '1');
  return url.href;
}
async function loadCatalog() {
  return fetch(sitePath('/static/motion-log/index.json'), {cache:'no-cache'}).then(r => {
    if (!r.ok) throw new Error('无法读取日志');
    return r.json();
  });
}
const outside = (url, label) => `<a class="pill-btn shadow" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label} ${icon('external')}</a>`;
function card(item) {
  return `<a data-link class="motion-card" href="${link(item.id)}">
    <div class="motion-cover">${item.cover ? `<img src="${esc(item.cover.startsWith('assets/') ? asset(item.id,item.cover) : item.cover)}" alt="${esc(item.title)}" loading="lazy" referrerpolicy="no-referrer">` : ''}<span class="motion-duration">${esc(item.duration)}</span></div>
    <div class="motion-card-meta"><time datetime="${item.date}">${item.date.replaceAll('-','.')}</time><span>${esc(item.brand)}</span></div>
    <h2>${esc(item.title)}</h2><p>${esc(item.intro)}</p>
    <span class="motion-read">阅读报告 ${icon('forward')}</span></a>`;
}

function reportStep(item, direction, compact = false) {
  const label = direction === 'prev' ? '上一篇' : '下一篇';
  const arrow = icon(direction === 'prev' ? 'back' : 'forward');
  if (!item) return compact
    ? `<button class="ibtn" type="button" disabled aria-label="${label}">${arrow}</button>`
    : `<span class="motion-step-empty">已是${direction === 'prev' ? '第一' : '最后一'}篇</span>`;
  const content = compact ? arrow : `<span>${direction === 'prev' ? arrow : ''}${label}${direction === 'next' ? arrow : ''}</span><b>${esc(item.title)}</b>`;
  return `<a data-link data-motion-step="${direction}" class="${compact ? 'ibtn' : 'motion-turn-link'}" href="${link(item.id)}" title="${label}：${esc(item.title)}" aria-label="${label}：${esc(item.title)}" aria-keyshortcuts="${direction === 'prev' ? 'ArrowLeft' : 'ArrowRight'}" rel="${direction}">${content}</a>`;
}

export async function renderMotionLog(view, id, signal) {
  const list = await loadCatalog();
  if (signal.aborted || !view.isConnected) return;
  if (!id) {
    view.innerHTML = `<header class="head"><h1>拉片日志</h1><span class="sub">${list.length} 篇单片报告 · 镜头、叙事与声音</span></header><div class="motion-grid">${list.map(card).join('') || VisionSite.emptyState({icon:'inbox',title:'还没有拉片报告',description:'单片分析报告发布后会显示在这里。'})}</div>`;
    hideBrokenCovers(view);
    return;
  }
  const index = list.findIndex(x => x.id === id);
  const item = list[index];
  const back = `<a class="pill-btn grey" data-link href="${link()}">${icon('back')} 拉片日志</a>`;
  if (!item) {view.innerHTML = VisionSite.emptyState({icon:'folder',title:'未收录这篇报告',description:'返回报告列表，查看已经收录的拉片日志。',actionsHTML:back}); return;}
  const previous = list[index - 1], next = list[index + 1];
  const response = await fetch(asset(id, 'report.html'), {signal});
  if (!response.ok) throw new Error('报告暂时无法读取');
  const html = await response.text();
  if (signal.aborted || !view.isConnected) return;
  document.title = item.title + ' · 拉片日志 · Vision Lab';
  view.innerHTML = `<div class="motion-toolbar"><div class="motion-toolbar-start">${back}<nav class="motion-pager" aria-label="切换拉片报告">${reportStep(previous,'prev',true)}<span aria-label="第 ${index + 1} 篇，共 ${list.length} 篇">${index + 1} / ${list.length}</span>${reportStep(next,'next',true)}</nav></div><div>${outside(item.sourcePage, '查看原片')}</div></div>
    <header class="motion-heading"><div class="motion-card-meta"><time>${item.date.replaceAll('-','.')}</time><span>拉片日志</span></div><h1>${esc(item.title)}</h1><p>${esc(item.creator)} · ${esc(item.duration)}</p></header>
    <div class="motion-layout"><div class="motion-main">
      <div class="motion-player-slot" id="motion-player"><section class="motion-player" aria-label="原片播放器">
        <a class="motion-player-return" href="#motion-player">回到原片 ${icon('external')}</a>
        <iframe src="${esc(autoplayEmbed(item.embed))}" title="${esc(item.title)} 原片" allow="autoplay; fullscreen; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>
      </section></div>
      <p class="motion-player-note">原片默认有声播放；若未自动开始，请点击播放。若播放器不可用，可<a href="${esc(item.sourcePage)}" target="_blank" rel="noopener noreferrer">查看原片 ${icon('external')}</a>。</p>
      ${item.missingAttachments ? `<p class="motion-source-note">完整报告正文已保留。${item.missingImages ? '部分关键帧与分析附件尚未收录，' : '部分分析附件尚未收录，'}下文保留对应说明和时间码。</p>` : item.externalAttachments ? '<p class="motion-source-note">关键画面、代表帧与高清联系表已收录。音频与分析数据链接在 Google Drive 中打开原文件。</p>' : ''}
      <article class="motion-report">${html}</article>
      <nav class="motion-report-turn" aria-label="继续阅读拉片报告">${reportStep(previous,'prev')}${reportStep(next,'next')}</nav>
      <footer class="motion-report-footer"><a class="pill-btn shadow" href="${asset(id,'report.md')}" download>下载报告 Markdown</a>${back}</footer>
    </div><aside class="motion-toc" aria-label="报告目录"><b>报告目录</b><a href="#motion-player">原片</a>${item.toc.map(h=>`<a href="#${esc(h.id)}">${esc(h.title)}</a>`).join('')}</aside></div>`;
  for (const element of view.querySelectorAll('[data-motion-asset]')) {
    element.setAttribute(element.tagName === 'IMG' ? 'src' : 'href', asset(id, element.dataset.motionAsset));
  }
  const frame = view.querySelector('iframe');
  signal.addEventListener('abort', () => frame.remove(), {once:true});
  mountReportNavigation(view, signal);
  mountReportPaging(view, signal);
  mountFrameViewer(view, signal);
}

function mountReportPaging(view, signal) {
  document.addEventListener('keydown', event => {
    if (signal.aborted || !view.isConnected || event.defaultPrevented || event.repeat || event.isComposing ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || document.fullscreenElement ||
        window.VisionMenu?.active || document.querySelector('dialog[open], .modal') ||
        event.target.closest('input, textarea, select, [contenteditable], [role="slider"], [role="tablist"], video, iframe') || event.target.matches('.motion-table')) return;
    const direction = {ArrowLeft:'prev', ArrowRight:'next'}[event.key];
    const target = direction && view.querySelector(`.motion-pager [data-motion-step="${direction}"]`);
    if (target) {event.preventDefault(); target.click();}
  }, {signal});
}

function mountReportNavigation(view, signal) {
  const player = view.querySelector('.motion-player');
  const slot = view.querySelector('.motion-player-slot');
  const links = [...view.querySelectorAll('.motion-toc a')];
  const sections = links.map(a => view.querySelector(a.getAttribute('href')));
  let scheduled = 0, anchorOffset = 24;
  const topInset = () => parseFloat(getComputedStyle(slot).scrollMarginTop) || 0;
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
    // Keep the same iframe in place: only its CSS position changes, preserving playback.
    player.classList.toggle('is-floating', slot.getBoundingClientRect().bottom <= topInset());
    const readingLine = anchorOffset + 8;
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
    anchorOffset = topInset() + 24;
    view.style.setProperty('--motion-floating-width', Math.max(220, slot.getBoundingClientRect().width / 2) + 'px');
    view.style.setProperty('--motion-anchor-offset', anchorOffset + 'px');
    schedule();
  }
  const observer = new ResizeObserver(measure);
  observer.observe(slot);
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
    window.scrollTo({top:scrollY + target.getBoundingClientRect().top - (target === slot ? topInset() : anchorOffset), behavior:'instant'});
    activate(target.id);
  }, {signal});
  measure();
}

function hideBrokenCovers(view) {
  for (const img of view.querySelectorAll('.motion-cover img')) {
    img.addEventListener('error', () => {img.hidden = true;}, {once:true});
  }
}
