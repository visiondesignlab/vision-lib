const {icon} = window.VisionSite;
/* User-facing instructions use the live navigation, public content and asset manifest. */
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const {path: sitePath, staticMode} = window.VisionSite;

export async function loadGuide() {
  const response = await fetch(sitePath('/static/guide-content.json'), {cache:'no-cache'});
  if (!response.ok) throw new Error('使用说明暂时无法加载');
  return response.json();
}

export function readNavigation() {
  const groups = [];
  for (const node of document.querySelector('#primaryNav').children) {
    if (node.matches('h2')) groups.push({name:node.textContent.trim(),items:[]});
    else if (node.matches('a[data-tab]') && node.dataset.tab !== 'guide') {
      // Only the link label belongs in the heading, not badges such as "new".
      const title = [...node.childNodes].filter(child => child.nodeType === Node.TEXT_NODE).map(child => child.textContent).join('').trim();
      groups.at(-1)?.items.push({id:node.dataset.tab,title,href:node.getAttribute('href')});
    }
  }
  return groups.filter(group => group.items.length);
}

export function renderGuide({content, types, cases, targets, casesLoaded}) {
  const element = document.createElement('div');
  element.className = 'site-guide';
  const groups = readNavigation();
  const count = type => cases.filter(item => item.type === type).length;
  element.innerHTML = `<header class="head"><h1>使用说明</h1><span class="sub">浏览内容、管理创作，使用团队工具与资产。</span></header>
    <div class="guide-intro"><p>从左侧选择栏目，内容会在当前页面打开。手机端可通过顶部菜单切换。</p><span class="muted">${casesLoaded ? `当前可浏览 ${cases.length} 条已发布内容` : '浏览、工具与资产的使用指南'}</span></div>
    ${groups.map(group => `<section class="guide-group" aria-label="${esc(group.name)}"><h2>${esc(group.name)}</h2><div class="guide-items">${group.items.map(item => {
      const help = content[item.id] || {}, steps = staticMode && help.publicSteps ? help.publicSteps : help.steps || [];
      return `<article class="guide-item" data-guide="${esc(item.id)}"><div class="guide-item-heading"><h3><a href="${esc(item.href)}" data-link>${esc(item.title)}<span aria-hidden="true">${icon('external')}</span></a></h3>${types[item.id] && casesLoaded ? `<span class="guide-count">${count(item.id)} 条已发布</span>` : ''}</div>
        <p class="guide-summary">${esc(types[item.id]?.sub || help.summary || `进入${item.title}查看当前功能。`)}</p>
        ${steps.length ? `<ol>${steps.map(step=>`<li>${esc(step)}</li>`).join('')}</ol>` : ''}
        ${help.note ? `<p class="guide-note">${esc(help.note)}</p>` : ''}
        ${item.id === 'brand-assets' ? '<div class="guide-assets" aria-live="polite"><span class="muted">正在读取当前资源…</span></div>' : ''}
      </article>`;
    }).join('')}</div></section>`).join('')}
    <section class="guide-group" aria-label="常见问题"><h2>常见问题</h2><div class="guide-faq">
      <details><summary>「使用」和「一键拉片」会自动发送吗？</summary><p>不会。选择工具后会准备提示词，由你在自己的工具中确认发送。当前可选：${targets.map(target=>esc(target.name)).join('、')}。上次选择会记在当前浏览器中，并同步到同站点的其他标签页。</p></details>
      <details><summary>没有打开 AI 工具怎么办？</summary><p>可以改选「复制 Prompt」，手动粘贴到自己的 AI 工具。是否能够分析视频，取决于该工具的能力和视频能否被读取。</p></details>
      <details><summary>为什么不同设备上的导航和预览布局不同？</summary><p>手机使用顶部菜单和适合触摸的按钮，桌面保留左侧导航。两种布局使用相同内容；动效会遵循系统的「减少动态效果」设置。</p></details>
      ${staticMode ? '<details><summary>内容如何更新到线上？</summary><p>线上站点展示已发布内容。内容在本机完成编辑与审核，重新发布网站后同步到线上。</p></details>' : '<details><summary>提交审核后，普通用户能看到吗？</summary><p>审核通过并发布后才会出现在浏览栏目。草稿、待审核内容和内部备注仅用于管理；已发布内容的新修订也要再次审核后才会替换线上版本。</p></details>'}
    </div></section>`;
  return element;
}

export async function updateGuideAssets(element) {
  const holder = element.querySelector('.guide-assets');
  if (!holder) return;
  try {
    const response = await fetch(sitePath('/static/assets/viaim/manifest.json'), {cache:'no-cache'});
    if (!response.ok) throw new Error('资源清单暂时不可用');
    const data = await response.json();
    holder.innerHTML = `<div class="guide-resource-links">${data.sections.map(section=>`<a class="pill-btn shadow" href="${esc(sitePath('/assets/brand?section='+encodeURIComponent(section.id)))}" data-link>${esc(section.name)}</a>`).join('')}</div>
      <p>${esc(data.brand)} 当前收录 ${Number(data.fileCount)} 个文件 · 品牌规范 ${esc(data.guideline.version)} · 公司介绍 ${data.companyIntros.length} 个版本 · 字体 ${data.fonts.length} 个字重</p>`;
  } catch {
    holder.innerHTML = `<p class="muted">资源信息暂时未能读取。可前往<a href="${sitePath('/assets/brand')}" data-link>品牌资产</a>查看。</p>`;
  }
}
