const {icon} = window.VisionSite;
/* viaim's existing public library, presented in Vision Lib's shared UI. */
import {createImageViewer, createPDFViewer} from './asset-viewer.js';
const sitePath = window.VisionSite.path;
const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const sizeLabel = bytes => bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
const defaultPreview = "viaim 品牌资产 / We Aim to Explore. / 让灵感、记录和知识更自然地流动。";
const loadedFonts = new Map();

export async function createBrandAssets({openPreview}) {
  const response = await fetch(sitePath("/static/assets/viaim/manifest.json"));
  if (!response.ok) throw new Error("Brand assets unavailable");
  const data = await response.json();
  const element = document.createElement("div");
  element.className = "brand-assets";
  let previewText = defaultPreview;
  let documentViewer = null;
  const $ = selector => element.querySelector(selector);
  const esc = escapeHTML;

  function href(section, options = {}) {
    const query = new URLSearchParams({section, ...options});
    return sitePath(`/assets/brand?${query}`);
  }
  function download(file, label, dark = false) {
    return `<a class="pill-btn ${dark ? "dark" : "shadow"}" href="${esc(file.downloadHref || file.href)}" download="${esc(file.fileName || "viaim 260309 Internal Draft.pdf")}" title="下载 ${esc(file.fileName || label)}">${esc(label)}</a>`;
  }
  function render(url) {
    deactivate();
    const section = data.sections.find(item => item.id === url.searchParams.get("section")) || data.sections[0];
    const counts = {"brand-guidelines": 1, "company-intro": data.companyIntros?.length || 0, "visual-assets": data.categories.reduce((total, category) => total + category.assets.length, 0), "font-packages": data.fonts.length};
    element.innerHTML = `<header class="head"><h1>品牌资产</h1><span class="sub">viaim 的品牌规范、公司介绍、视觉资产与字体</span><div class="right"><span class="tag">viaim</span></div></header>
      <nav class="bar" aria-label="品牌资产分类"><div class="chips">${data.sections.map(item => `<a class="chip ${item.id === section.id ? "on" : ""}" href="${href(item.id)}" data-link ${item.id === section.id ? 'aria-current="page"' : ""}>${esc(item.name)}${counts[item.id] ? `<span class="n">${counts[item.id]}</span>` : ""}</a>`).join("")}</div></nav>
      <section id="brandContent" aria-label="${esc(section.name)}"></section>`;
    if (section.id === "brand-guidelines") renderGuidelines();
    else if (section.id === "company-intro") renderCompanyIntros(url);
    else if (section.id === "visual-assets") renderLogos(url);
    else if (section.id === "font-packages") renderFonts(url);
    else $("#brandContent").innerHTML = `<div class="brand-empty"><span class="brand-empty-mark" aria-hidden="true">${icon('plus')}</span><h2>暂无${esc(section.name)}</h2><p>此分类尚未收录内容。</p></div>`;
  }

  function renderGuidelines() {
    const g = data.guideline;
    $("#brandContent").innerHTML = `<div class="brand-document-layout">
      <article class="brand-surface brand-document-info">
        <span class="brand-eyebrow">品牌规范</span><h2>${esc(g.title)}</h2>
        <p class="brand-description">${esc(g.summary)}</p>
        <div class="brand-actions">${download(g, "下载 PDF", true)}<button type="button" class="pill-btn shadow" data-document-preview="${esc(g.href)}" aria-haspopup="dialog">大图预览</button></div>
        <dl class="brand-meta">${[["版本", g.version],["状态", g.statusLabel || "当前版本 · 内部草案"],["格式", g.format],["文件大小", sizeLabel(g.bytes)],["源文件日期", g.sourceDate],["收录日期", g.updatedAt]].map(([label,value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>
        <section class="brand-history"><h3>版本历史 <span class="tag">${data.versions.length}</span></h3>${data.versions.map(version => `<button type="button" ${version.href ? `data-document-preview="${esc(version.href)}" aria-haspopup="dialog"` : 'disabled'}><span class="brand-version-title">${esc(version.version)}<span class="tag">${version.status === 'current' ? '当前' : '历史版本'}</span></span><span class="muted">${esc(version.date)}</span><p>${esc(version.note)}</p></button>`).join("")}</section>
      </article>
      <section class="brand-surface brand-document-preview" aria-label="品牌规范 PDF 预览"><div class="brand-section-head"><h2>文档预览</h2><span class="muted">${esc(g.version)}</span></div><div class="brand-pdf"></div></section>
    </div>`;
    mountDocument(g);
  }

  function renderCompanyIntros(url) {
    const documents = data.companyIntros || [];
    const selected = documents.find(item => item.id === url.searchParams.get("document")) || documents[0];
    if (!selected) {
      $("#brandContent").innerHTML = '<div class="brand-empty"><h2>暂无公司介绍</h2><p>此分类尚未收录内容。</p></div>';
      return;
    }
    $("#brandContent").innerHTML = `<div class="brand-document-layout">
      <article class="brand-surface brand-document-info">
        <span class="brand-eyebrow">公司介绍</span><h2>viaim 公司品牌介绍</h2>
        <nav class="brand-document-options" aria-label="公司介绍版本">${documents.map(item => `<a href="${href("company-intro",{document:item.id})}" data-link ${item.id === selected.id ? 'aria-current="true"' : ""}><span><b>${esc(item.label)}</b><small>${esc(item.version)} · ${item.pages} 页</small></span><span class="muted">${sizeLabel(item.bytes)}</span></a>`).join("")}</nav>
        <h3>${esc(selected.label)}</h3><p class="brand-document-filename">${esc(selected.fileName)}</p>
        <div class="brand-actions">${download(selected,"下载 PDF",true)}<button type="button" class="pill-btn shadow" data-document-preview="${esc(selected.href)}" aria-haspopup="dialog">大图预览</button></div>
        <dl class="brand-meta">${[["版本",selected.version],["格式",selected.format],["页数",`${selected.pages} 页`],["文件大小",sizeLabel(selected.bytes)],["收录日期",selected.addedAt]].map(([label,value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>
      </article>
      <section class="brand-surface brand-document-preview" aria-label="公司介绍 PDF 预览"><div class="brand-section-head"><h2>${esc(selected.label)} · 文档预览</h2><span class="muted">${esc(selected.version)}</span></div><div class="brand-pdf"></div></section>
    </div>`;
    mountDocument(selected);
  }

  function mountDocument(selected) {
    documentViewer = createPDFViewer($('.brand-pdf'), {href: selected.href, title: selected.title});
    element.querySelectorAll('[data-document-preview]').forEach(button => {
      button.onclick = () => {
        const documents = [data.guideline, ...data.companyIntros].map(file => ({
          kind: 'pdf', title: `${file.title}${file.label ? ` · ${file.label}` : ''}`, category: file.label ? '公司介绍' : '品牌规范',
          previewHref: file.href, initialPage: file.href === selected.href ? documentViewer.pageNumber : 1,
          usage: file.summary || file.fileName,
          metadata: [['版本',file.version],['页数',file.pages ? `${file.pages} 页` : null],['文件大小',sizeLabel(file.bytes)]],
          formats: [{label:'PDF', href:file.downloadHref || file.href, fileName:file.fileName || 'viaim 260309 Internal Draft.pdf'}],
        }));
        const index = documents.findIndex(file => file.previewHref === button.dataset.documentPreview);
        if (index >= 0) openPreview(documents, index, '品牌文档', button);
      };
    });
  }
  function deactivate() { documentViewer?.destroy(); documentViewer = null; }

  function renderLogos(url) {
    const category = data.categories.find(item => item.id === url.searchParams.get("category")) || data.categories[0];
    const view = url.searchParams.get("view") === "list" ? "list" : "grid";
    let query = url.searchParams.get("q") || "";
    const options = {category: category.id, view, ...(query ? {q:query} : {})};
    $("#brandContent").innerHTML = `<div class="brand-toolbar">
      <nav class="brand-subnav" aria-label="Logo 分类">${data.categories.map(item => `<a href="${href("visual-assets",{...options,category:item.id})}" data-link ${item.id === category.id ? 'aria-current="page"' : ""}>${esc(item.label)}<span>${item.assets.length}</span></a>`).join("")}</nav>
      <div class="brand-toolbar-right"><input type="search" class="search" id="brandSearch" aria-label="搜索 Logo" placeholder="搜索 Logo" value="${esc(query)}"><div class="brand-view-switch" aria-label="Logo 展示方式">${[["grid","平铺"],["list","列表"]].map(([value,label]) => `<a class="pill-btn ${view === value ? "grey" : ""}" href="${href("visual-assets",{...options,view:value})}" data-link ${view === value ? 'aria-current="true"' : ""}>${label}</a>`).join("")}</div></div>
      </div><div class="brand-collection-summary"><p>${esc(category.summary)}</p><span id="brandLogoCount"></span></div><div class="brand-logo-gallery" data-view="${view}" id="brandLogoGallery"></div>`;
    function updateGallery() {
      const list = category.assets.filter(asset => [asset.title,asset.context,asset.usage,...asset.formats.map(format => format.label)].join(" ").toLowerCase().includes(query.trim().toLowerCase()));
      $("#brandLogoCount").textContent = `${list.length} 组 · ${list.reduce((total,asset) => total + asset.formats.length,0)} 个文件`;
      $("#brandLogoGallery").innerHTML = list.length ? list.map(asset => `<article class="brand-logo-card">
        <button type="button" class="brand-logo-preview ${category.id === "app" ? "brand-app-preview" : ""}" aria-label="预览 ${esc(asset.title)}" aria-haspopup="dialog"><img src="${esc(asset.previewHref)}" alt="${esc(asset.title)}" loading="lazy"></button>
        <div class="brand-logo-copy"><span class="brand-eyebrow">${esc(asset.context)}</span><h2>${esc(asset.title)}</h2><p>${esc(asset.usage)}</p><span class="muted brand-dimensions">${esc(asset.dimensions)}</span></div>
        <div class="brand-format-links">${asset.formats.map(format => `<a href="${esc(format.href)}" download="${esc(format.fileName)}" class="pill-btn shadow" title="下载 ${esc(format.fileName)} · ${sizeLabel(format.bytes)}">${esc(format.label)}<span>${sizeLabel(format.bytes)}</span></a>`).join("")}</div>
      </article>`).join("") : '<div class="brand-empty"><h2>没有匹配的 Logo</h2><p>换个关键词试试。</p></div>';
      element.querySelectorAll(".brand-logo-preview").forEach((button, index) => {
        button.addEventListener("click", () => openPreview(list, index, category.label, button));
      });
    }
    $("#brandSearch").addEventListener("input", event => {
      query = event.target.value;
      const current = new URL(location.href);
      if (query) current.searchParams.set("q", query); else current.searchParams.delete("q");
      history.replaceState({}, "", current);
      // Keep subsequent category/view switches aligned with the visible query.
      element.querySelectorAll(".brand-toolbar a[data-link]").forEach(link => {
        const next = new URL(link.href);
        if (query) next.searchParams.set("q", query); else next.searchParams.delete("q");
        link.href = next.pathname + next.search;
      });
      updateGallery();
    });
    updateGallery();
  }

  function renderFonts(url) {
    const font = data.fonts.find(item => item.id === url.searchParams.get("font")) || data.fonts[4];
    $("#brandContent").innerHTML = `<div class="brand-font-layout">
      <section class="brand-surface brand-font-list"><div class="brand-section-head"><h2>MiSans</h2><span class="tag">${data.fonts.length} 个字重</span></div><nav aria-label="MiSans 字重">${data.fonts.map(item => `<a href="${href("font-packages",{font:item.id})}" data-link ${font.id === item.id ? 'aria-current="true"' : ""}><span><b>${esc(item.label)}</b><small>${esc(item.fileName)} · ${sizeLabel(item.bytes)}</small></span><span class="muted">${item.weight}</span></a>`).join("")}</nav></section>
      <section class="brand-surface brand-font-detail" data-font-id="${esc(font.id)}"><div class="brand-section-head"><h2>${esc(font.label)}</h2>${download(font,"下载 OTF",true)}</div>
        <label class="brand-font-editor" for="brandFontText">预览文本<textarea id="brandFontText" rows="3" spellcheck="false">${esc(previewText)}</textarea></label>
        <div class="brand-font-state" role="status">字体加载中…</div>
        <div class="brand-type-stage" style="--brand-font-weight:${font.weight}" aria-busy="true"><div class="brand-font-preview"><span class="brand-eyebrow">${esc(font.role)}</span><p class="brand-preview-text"></p></div>
          <div class="brand-font-samples"><div><span>展示 · 42px</span><strong style="font-size:42px">viaim</strong></div><div><span>标题 · 28px</span><strong style="font-size:28px">We Aim to Explore.</strong></div><div><span>正文 · 16px</span><strong style="font-size:16px">实时记录、整理和理解每一次重要对话。</strong></div></div>
        </div><dl class="brand-meta brand-font-meta">${[["字体家族","MiSans"],["字重",font.weight],["文件",font.fileName],["文件大小",sizeLabel(font.bytes)]].map(([label,value]) => `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>
      </section></div>`;
    $(".brand-preview-text").textContent = previewText.trim() || defaultPreview;
    $("#brandFontText").addEventListener("input", event => {
      previewText = event.target.value;
      $(".brand-preview-text").textContent = previewText.trim() || defaultPreview;
    });
    const detail = $(".brand-font-detail");
    if (!loadedFonts.has(font.id)) {
      const face = new FontFace("ViaimAssetMiSans", `url("${font.href}")`, {weight:String(font.weight)});
      loadedFonts.set(font.id, face.load().then(loaded => { document.fonts.add(loaded); return loaded; }).catch(error => { loadedFonts.delete(font.id); throw error; }));
    }
    loadedFonts.get(font.id).then(() => {
      detail.querySelector(".brand-font-state").textContent = `${font.label} · 预览已就绪`;
      detail.querySelector(".brand-type-stage").setAttribute("aria-busy", "false");
    }).catch(() => { detail.querySelector(".brand-font-state").textContent = "字体预览加载失败，可重新选择字重重试或下载源文件。"; });
  }
  return {element, render, deactivate, createImageViewer, createPDFViewer};
}
