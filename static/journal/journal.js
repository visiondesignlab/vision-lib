const {path: sitePath, icon} = window.VisionSite;
import {mountJournalFilms} from './films.js';
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link = vol => sitePath('/journal' + (vol ? '?vol=' + vol : ''));
const asset = (vol, file) => sitePath('/static/journal/' + vol + '/' + file);
let catalog;

async function get(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error('日刊暂时无法读取');
  return response;
}
function issues() {
  return catalog ||= get(sitePath('/static/journal/issues.json')).then(r => r.json()).catch(error => { catalog = null; throw error; });
}
function card(issue, latest = false) {
  const {volume, headline, date, intro} = issue;
  return `<a data-link href="${link(volume)}" class="journal-card${latest ? ' journal-latest' : ''}">
    <div class="journal-media"><img src="${asset(volume,'cover.webp')}" alt="" ${latest ? '' : 'loading="lazy"'}></div>
    <div class="journal-caption">
      <div class="journal-meta">${latest ? '<span>最新一期</span>' : ''}<b>Vol.${volume}</b><time datetime="${date}">${date.replaceAll('-','.')} </time></div>
      <h2>${esc(headline)}</h2><p>${esc(intro)}</p>
      ${latest ? `<span class="journal-read">阅读本期 ${icon('forward')}</span>` : ''}
    </div></a>`;
}
function archive(list) {
  return `<header class="head"><h1>有点意思</h1><span class="sub">Vision Design 设计日报</span></header>
    ${card(list[0], true)}
    ${list.length > 1 ? `<section class="journal-backlist"><h2>往期日刊 <span>${list.length - 1} 期</span></h2>
      <div class="journal-grid">${list.slice(1).map(item => card(item)).join('')}</div></section>` : ''}`;
}
const back = () => `<a data-link class="pill-btn grey" href="${link()}">${icon('back')} 全部期刊</a>`;
export async function renderJournal(view, requested, signal) {
  const list = await issues();
  if (!view.isConnected) return;
  if (requested === null) {
    view.innerHTML = list.length ? archive(list) : VisionSite.emptyState({title:'还没有日刊',description:'收录后的日刊会按期显示在这里。'});
    return;
  }
  const index = list.findIndex(item => String(item.volume) === requested);
  if (index < 0) {
    view.innerHTML = VisionSite.emptyState({icon:'folder',title:'未收录这一期日刊',description:'返回全部期刊，查看已经收录的日刊。',actionsHTML:back()});
    return;
  }
  const current = list[index];
  const url = asset(current.volume, 'article.html');
  const html = await (await get(url)).text();
  if (!view.isConnected) return;
  document.title = `Vol.${current.volume} 有点意思 · Vision Lab`;
  view.innerHTML = `<nav class="journal-toolbar" aria-label="日刊导航">${back()}</nav>
    <article class="journal-article"></article>
    <nav class="journal-turn" aria-label="切换期刊">
      ${list[index + 1] ? `<a data-link href="${link(list[index + 1].volume)}">${icon('previous')} 上一期 · Vol.${list[index + 1].volume}</a>` : '<span></span>'}
      ${list[index - 1] ? `<a data-link href="${link(list[index - 1].volume)}">下一期 · Vol.${list[index - 1].volume} ${icon('next')}</a>` : ''}
    </nav>`;
  const template = document.createElement('template');
  template.innerHTML = html;
  for (const image of template.content.querySelectorAll('img')) {
    image.setAttribute('src', asset(current.volume, image.getAttribute('src')));
  }
  for (const source of template.content.querySelectorAll('a.source-url[href]')) {
    source.insertAdjacentHTML('beforeend', icon('external'));
  }
  view.querySelector('article').append(template.content);
  if (!signal.aborted) mountJournalFilms(view, signal);
}
