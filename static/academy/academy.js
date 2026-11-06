const {path: sitePath, icon} = window.VisionSite;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));

export async function loadAcademy() {
  const response = await fetch(sitePath('/static/academy/catalog.json'), {cache:'no-cache'});
  if (!response.ok) throw new Error('课程目录暂时无法加载');
  return response.json();
}

export function academyPage(entries) {
  const page = document.createElement('section');
  page.className = 'academy-page';
  page.innerHTML = `<header class="head"><h1>AI 学堂</h1><span class="sub">官方课程、教程与创作方法</span></header>
    <div class="academy-intro"><h2>探索 AI 学习资源</h2><p>找到适合自己的学习方向，从课程、教程与创作案例中积累方法。</p></div>
    <div class="academy-grid">${entries.map(entry => `<a class="academy-card" href="${esc(entry.url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(entry.name)}，${esc(entry.action || '浏览官方课程')}（新标签页）">
      <div class="academy-card-heading"><img src="${esc(sitePath(entry.icon))}" width="36" height="36" alt=""><div><h3>${esc(entry.name)}</h3><span class="muted">${esc(entry.provider)} · ${esc(entry.kind || '官方学院')}</span></div></div>
      <p class="academy-description">${esc(entry.description)}</p>
      <ul class="academy-topics" aria-label="学习方向">${entry.topics.map(topic => `<li>${esc(topic)}</li>`).join('')}</ul>
      <span class="academy-card-footer">${esc(entry.action || '浏览课程')} ${icon('external')}</span>
    </a>`).join('')}</div>`;
  return page;
}
