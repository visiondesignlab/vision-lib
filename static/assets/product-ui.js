import '../vendor/jszip.min.js';
import {createScreenshotExporter} from './product-ui-export.js';

const {path:sitePath, icon, emptyState} = window.VisionSite;
const {enhanceSelect} = window.VisionMenu;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const modes = {raw:'原生截图',shadow:'Mockup · 有底部阴影',clean:'Mockup · 无底部阴影'};

export async function createProductUI({catalogHref, openPreview}) {
  const catalogURL = new URL(sitePath(catalogHref),location.origin).href;
  const response = await fetch(catalogURL);
  if (!response.ok) throw new Error('产品界面素材暂时无法加载');
  const data = await response.json(), exporter = createScreenshotExporter(data,catalogURL);
  const element = document.createElement('div'); element.className = 'product-ui';
  const $ = selector => element.querySelector(selector);
  const state = {locale:data.locales[0].id,mode:'raw',scale:3,current:data.items[0].id,query:'',selected:new Set(),background:'checker',busy:false};
  let active = false, generation = 0, lifetime = 0, previewURL = null;
  const thumbnailURLs = new Set(), downloads = new Set();
  const config = () => ({locale:state.locale,mode:state.mode,scale:state.scale});
  const localeName = () => data.locales.find(locale => locale.id === state.locale).label;
  const filtered = () => data.items.filter(item => [item.id,item.name,item.module].join(' ').toLowerCase().includes(state.query.trim().toLowerCase()));
  function releaseThumbnails() { thumbnailURLs.forEach(url => URL.revokeObjectURL(url)); thumbnailURLs.clear(); }
  function deactivate() {
    active = false; generation++; lifetime++; releaseThumbnails();
    if (previewURL) URL.revokeObjectURL(previewURL); previewURL = null;
  }
  function syncURL() {
    if (!active) return;
    const url = new URL(location.href);
    for (const [key,value] of Object.entries({locale:state.locale,export:state.mode,scale:state.scale,shot:state.current,q:state.query})) {
      if (value === '') url.searchParams.delete(key); else url.searchParams.set(key,String(value));
    }
    history.replaceState({},'',url);
  }
  function message(text,error = false) {
    if (!active) return;
    const holder = $('.ui-export-status'); holder.textContent = text;
    holder.setAttribute('role',error ? 'alert' : 'status');
  }
  function selectionUI() {
    if (!active) return;
    $('.ui-selection-count').textContent = `已选择 ${state.selected.size} 张 · ${localeName()}`;
    const items = filtered(), all = items.length && items.every(item => state.selected.has(item.id));
    $('[data-ui-action=all]').textContent = all ? '取消当前结果全选' : '全选当前结果';
    $('[data-ui-action=all]').disabled = !items.length;
    $('[data-ui-action=clear]').disabled = !state.selected.size;
    $('[data-ui-action=zip]').textContent = `打包下载所选（${state.selected.size}）`;
    $('[data-ui-action=zip]').disabled = state.busy || !state.selected.size;
    $('[data-ui-action=download]').disabled = state.busy;
    element.querySelectorAll('[data-ui-download]').forEach(button => button.disabled = state.busy);
    element.querySelectorAll('.ui-shot-card input').forEach(input => input.checked = state.selected.has(input.closest('[data-shot]').dataset.shot));
  }
  function render(url) {
    deactivate(); active = true;
    const locale = url.searchParams.get('locale'), mode = url.searchParams.get('export'), scale = Number(url.searchParams.get('scale'));
    if (data.locales.some(item => item.id === locale)) state.locale = locale;
    if (Object.hasOwn(modes,mode)) state.mode = mode;
    if ([1,2,3].includes(scale)) state.scale = scale;
    if (data.items.some(item => item.id === url.searchParams.get('shot'))) state.current = url.searchParams.get('shot');
    state.query = url.searchParams.get('q') || '';
    element.innerHTML = `<div class="brand-toolbar">
      <div class="ui-library-meta"><h2>产品界面</h2><span class="muted">${esc(data.sourceLabel)} · ${esc(data.device)}</span></div>
      <div class="brand-toolbar-right"><input class="search" type="search" aria-label="搜索产品界面" placeholder="搜索页面、模块" value="${esc(state.query)}"><a class="pill-btn shadow" href="${esc(data.figmaUrl)}" target="_blank" rel="noopener">Figma 源文件 ${icon('external')}</a></div>
    </div>
    <div class="brand-collection-summary"><p>${data.items.length} 个页面 · ${data.locales.length} 种语言 · 原生截图与设备 mockup</p><span>示例素材 · 批次 ${esc(data.sourceCommit.slice(0,9))}</span></div>
    <div class="ui-workspace"><section class="ui-gallery-section" aria-label="产品截图列表">
      <div class="ui-selection-bar"><span class="ui-selection-count" role="status"></span><div><button type="button" class="pill-btn shadow" data-ui-action="all">全选当前结果</button><button type="button" class="pill-btn grey" data-ui-action="clear">清空选择</button></div></div>
      <div class="ui-shot-grid"></div>
    </section>
    <aside class="brand-surface ui-export-panel" aria-label="预览与下载">
      <div class="brand-section-head"><h2>预览与下载</h2><span class="tag">PNG</span></div>
      <button type="button" class="ui-preview-stage" data-background="${state.background}" aria-label="放大预览当前截图" aria-haspopup="dialog"><img alt="当前截图预览"></button>
      <div class="ui-preview-caption"><h3 class="ui-current-name"></h3><div class="ui-backgrounds" role="group" aria-label="预览底色">${[['checker','透明'],['white','白色'],['dark','深色']].map(([value,label]) => `<button type="button" class="pill-btn ${state.background === value ? 'grey' : ''}" data-background="${value}" aria-pressed="${state.background === value}">${label}</button>`).join('')}</div></div>
      <div class="ui-export-fields">
        <label for="ui-locale">截图语言<select id="ui-locale">${data.locales.map(locale => `<option value="${esc(locale.id)}" ${state.locale === locale.id ? 'selected' : ''}>${esc(locale.label)}</option>`).join('')}</select></label>
        <label for="ui-mode">导出样式<select id="ui-mode">${Object.entries(modes).map(([value,label]) => `<option value="${value}" ${state.mode === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        <label for="ui-scale">导出倍率<select id="ui-scale">${[3,2,1].map(scale => `<option value="${scale}" ${state.scale === scale ? 'selected' : ''}>@${scale}x${scale === 3 ? ' · 默认' : ''}</option>`).join('')}</select></label>
      </div>
      <p class="ui-dimensions"></p>
      <div class="ui-download-actions"><button type="button" class="pill-btn dark" data-ui-action="download">${icon('download')} 下载当前图片</button><button type="button" class="pill-btn shadow" data-ui-action="zip" disabled>打包下载所选（0）</button></div>
      <p class="ui-download-hint">原生 @3x 保留直角和完整画面。Mockup 导出透明 PNG，底色仅用于预览。</p>
      <p class="ui-export-status" role="status" aria-live="polite"></p>
    </aside></div>`;
    for (const [id,label] of [['ui-locale','截图语言'],['ui-mode','导出样式'],['ui-scale','导出倍率']]) enhanceSelect($('#'+id),label,true);
    $('#ui-locale').onchange = event => { state.locale = event.target.value; syncURL(); updateGallery(); updatePreview(); };
    $('#ui-mode').onchange = event => { state.mode = event.target.value; syncURL(); updateGallery(); updatePreview(); };
    $('#ui-scale').onchange = event => { state.scale = Number(event.target.value); syncURL(); updatePreview(); };
    $('.search').oninput = event => { state.query = event.target.value; syncURL(); updateGallery(); };
    $('[data-ui-action=all]').onclick = () => {
      const items = filtered(), all = items.every(item => state.selected.has(item.id));
      items.forEach(item => all ? state.selected.delete(item.id) : state.selected.add(item.id)); selectionUI();
    };
    $('[data-ui-action=clear]').onclick = () => { state.selected.clear(); selectionUI(); };
    $('[data-ui-action=download]').onclick = () => download([state.current],false);
    $('[data-ui-action=zip]').onclick = () => download([...state.selected],true);
    $('.ui-preview-stage').onclick = showPreview;
    element.querySelectorAll('.ui-backgrounds button').forEach(button => button.onclick = () => {
      state.background = button.dataset.background; $('.ui-preview-stage').dataset.background = state.background;
      element.querySelectorAll('.ui-backgrounds button').forEach(item => { item.setAttribute('aria-pressed',item === button); item.classList.toggle('grey',item === button); });
    });
    syncURL(); updateGallery(); updatePreview();
  }
  function updateGallery() {
    const token = ++generation, settings = config(), items = filtered(); releaseThumbnails();
    let thumbnails = Promise.resolve();
    $('.ui-shot-grid').innerHTML = items.length ? items.map(item => `<article class="brand-logo-card ui-shot-card" data-shot="${esc(item.id)}" ${state.current === item.id ? 'data-current="true"' : ''}>
      <div class="ui-shot-top"><span>${esc(item.id)}</span><input type="checkbox" aria-label="选择 ${esc(item.name)}"></div>
      <button type="button" class="ui-shot-image" aria-label="预览 ${esc(item.name)}" aria-pressed="${state.current === item.id}"><img src="${esc(exporter.resolve(item.locales[state.locale].src))}" alt="${esc(item.name)} · ${esc(localeName())}" loading="lazy" width="1260" height="2736"></button>
      <div class="brand-logo-copy"><h3>${esc(item.name)}</h3><p>${esc(item.module)}</p><div class="ui-shot-actions"><button type="button" class="pill-btn grey" data-ui-choose>预览</button><button type="button" class="ibtn" data-ui-download aria-label="下载 ${esc(item.name)}">${icon('download')}</button></div></div></article>`).join('') : emptyState({icon:'search',title:'没有匹配的产品界面',description:'试试页面名称、模块或页面编号。'});
    element.querySelectorAll('.ui-shot-card').forEach(card => {
      const id = card.dataset.shot;
      card.querySelector('input').onchange = event => { event.target.checked ? state.selected.add(id) : state.selected.delete(id); selectionUI(); };
      const choose = () => {
        state.current = id; syncURL();
        element.querySelectorAll('.ui-shot-card').forEach(item => {
          item.toggleAttribute('data-current',item === card); item.querySelector('.ui-shot-image').setAttribute('aria-pressed',item === card);
        }); updatePreview();
      };
      card.querySelector('.ui-shot-image').onclick = choose; card.querySelector('[data-ui-choose]').onclick = choose;
      card.querySelector('[data-ui-download]').onclick = () => download([id],false);
      const image = card.querySelector('img');
      image.onerror = () => { image.hidden = true; card.querySelector('.ui-shot-image').textContent = '图片未能加载，点击预览可重试。'; };
      // Keep the full-size preview responsive while a language switch prepares cards.
      if (settings.mode !== 'raw') thumbnails = thumbnails.then(async () => {
        if (!active || token !== generation) return;
        const blob = await exporter.render(id,{...settings,scale:1});
        if (!active || token !== generation) return;
        const url = URL.createObjectURL(blob); thumbnailURLs.add(url); image.src = url;
      }).catch(error => { if (active && token === generation) message(error.message,true); });
    });
    selectionUI();
  }
  let previewToken = 0;
  async function updatePreview() {
    const token = ++previewToken, mount = lifetime, id = state.current, settings = config();
    const item = data.items.find(item => item.id === id), stage = $('.ui-preview-stage');
    const [width,height] = exporter.dimensions(settings.mode,settings.scale);
    $('.ui-current-name').textContent = item.name;
    $('.ui-dimensions').textContent = `${width} × ${height} px · @${settings.scale}x · ${settings.mode === 'raw' ? '直角原图' : '透明 PNG'}`;
    stage.setAttribute('aria-busy','true'); stage.disabled = true;
    try {
      const blob = await exporter.render(id,settings);
      if (!active || token !== previewToken || mount !== lifetime) return;
      const url = URL.createObjectURL(blob), image = stage.querySelector('img');
      image.hidden = false; image.src = url; image.alt = `${item.name} · ${localeName()} · ${modes[settings.mode]}`;
      if (previewURL) URL.revokeObjectURL(previewURL); previewURL = url;
    } catch (error) {
      if (active && token === previewToken) {
        if (previewURL) URL.revokeObjectURL(previewURL); previewURL = null;
        stage.querySelector('img').hidden = true;
        message(error.message,true);
      }
    }
    finally { if (active && token === previewToken) { stage.setAttribute('aria-busy','false'); stage.disabled = !previewURL; } }
  }
  function showPreview() {
    if (!previewURL) return;
    const item = data.items.find(item => item.id === state.current), name = exporter.filename(item.id,config());
    openPreview([{title:item.name,category:'产品界面',usage:`${localeName()} · ${modes[state.mode]} · @${state.scale}x`,previewHref:previewURL,
      metadata:[['设备',data.device],['版本',data.version],['尺寸',$('.ui-dimensions').textContent]],formats:[{label:'PNG',href:previewURL,fileName:name}]}],0,'产品界面',$('.ui-preview-stage'));
  }
  function save(blob,name) {
    const url = URL.createObjectURL(blob), anchor = document.createElement('a'); downloads.add(url);
    anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => { URL.revokeObjectURL(url); downloads.delete(url); },60000);
  }
  async function download(ids,zipped) {
    if (state.busy || !ids.length) return;
    const settings = config(); state.busy = true; selectionUI(); message('正在准备图片…');
    try {
      if (!zipped) save(await exporter.render(ids[0],settings),exporter.filename(ids[0],settings));
      else {
        const zip = new window.JSZip();
        for (let i = 0; i < ids.length; i++) {
          message(`正在准备 ${i+1} / ${ids.length} 张图片…`);
          zip.file(exporter.filename(ids[i],settings),await (await exporter.render(ids[i],settings)).arrayBuffer());
        }
        zip.file('说明.txt',`viaim Capture V6\n版本：${data.version}\n截图批次：${data.sourceCommit}\n语言：${settings.locale}\n样式：${modes[settings.mode]}\n倍率：@${settings.scale}x\n图片数量：${ids.length}\n原生 @3x 保留源 PNG 字节；其他倍率经过缩放。\n`);
        save(await zip.generateAsync({type:'blob'}),`viaim-capture_${settings.locale}_${settings.mode}@${settings.scale}x_${ids.length}张.zip`);
      }
      message('文件已生成，已发起下载。');
    } catch (error) { message(error.message || '导出失败，请重试。',true); }
    finally { state.busy = false; selectionUI(); }
  }
  return {element,render,deactivate,count:data.items.length,assetCount:data.items.reduce((sum,item) => sum+Object.keys(item.locales).length,0)};
}
