const sitePath = window.VisionSite.path;
/* Shared, local image/PDF reader. Zoom is relative to the fitted view. */
const icons = {
  minus: '<path d="M2.5 6h7"/>', plus: '<path d="M2.5 6h7M6 2.5v7"/>',
  previous: '<path d="m7.5 2.5-3.5 3.5 3.5 3.5"/>', next: '<path d="m4.5 2.5 3.5 3.5-3.5 3.5"/>',
};
const icon = name => `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">${icons[name]}</svg>`;
const button = (action, label, glyph) => `<button type="button" class="ibtn" data-viewer-action="${action}" title="${label}" aria-label="${label}">${icon(glyph)}</button>`;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function createViewport(host, {onBackdrop = () => {}} = {}) {
  host.innerHTML = `<div class="asset-viewer">
    <div class="asset-viewport" tabindex="0" aria-label="图片预览，可放大后拖拽查看"><div class="frame asset-viewer-frame"></div><div class="asset-viewer-status" role="status"></div></div>
    <div class="asset-viewer-toolbar" aria-label="预览工具">
      <div class="asset-zoom-controls">${button('zoom-out','缩小','minus')}<span class="asset-zoom-value" title="相对适应窗口的比例">100%</span>${button('zoom-in','放大','plus')}<button type="button" class="pill-btn grey" data-viewer-action="fit">适应窗口</button></div>
    </div></div>`;
  const root = host.firstElementChild, viewport = root.querySelector('.asset-viewport');
  const frame = root.querySelector('.asset-viewer-frame'), status = root.querySelector('.asset-viewer-status');
  const zoomOut = root.querySelector('[data-viewer-action="zoom-out"]'), zoomIn = root.querySelector('[data-viewer-action="zoom-in"]');
  let width = 0, height = 0, fit = 1, zoom = 1, x = 0, y = 0, pointer = null, suppressClick = false;
  const touches = new Map();
  let pinch = null;
  function bounds() { return {x: Math.max(0, (width * fit * zoom - viewport.clientWidth + 48) / 2), y: Math.max(0, (height * fit * zoom - viewport.clientHeight + 48) / 2)}; }
  function update() {
    if (!width || !height) return;
    fit = Math.min((viewport.clientWidth - 48) / width, (viewport.clientHeight - 48) / height, 1);
    fit = Math.max(.01, fit);
    const limit = bounds(); x = clamp(x, -limit.x, limit.x); y = clamp(y, -limit.y, limit.y);
    frame.style.width = `${width * fit}px`; frame.style.height = `${height * fit}px`;
    frame.style.transform = `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${zoom})`;
    root.querySelector('.asset-zoom-value').textContent = `${Math.round(zoom * 100)}%`;
    zoomOut.disabled = zoom <= .25; zoomIn.disabled = zoom >= 8;
    viewport.classList.toggle('can-pan', limit.x > 0 || limit.y > 0);
  }
  function setZoom(value, anchor) {
    const next = clamp(value, .25, 8), ratio = next / zoom;
    x = anchor ? anchor.x - (anchor.x - x) * ratio : x * ratio;
    y = anchor ? anchor.y - (anchor.y - y) * ratio : y * ratio;
    zoom = next; update();
  }
  function reset() { zoom = 1; x = y = 0; update(); }
  zoomOut.onclick = () => setZoom(zoom / 1.25);
  zoomIn.onclick = () => setZoom(zoom * 1.25);
  root.querySelector('[data-viewer-action="fit"]').onclick = reset;
  root.addEventListener('keydown', event => {
    if (event.target.matches('input') || event.ctrlKey || event.metaKey || event.altKey) return;
    if (['+', '=', '-', '0'].includes(event.key)) {
      event.preventDefault(); event.stopPropagation();
      if (event.key === '0') reset(); else setZoom(zoom * (event.key === '-' ? .8 : 1.25));
    }
  });
  viewport.addEventListener('wheel', event => {
    event.preventDefault();
    const rect = viewport.getBoundingClientRect();
    setZoom(zoom * Math.exp(-clamp(event.deltaY, -100, 100) * .002), {x: event.clientX - rect.left - rect.width / 2, y: event.clientY - rect.top - rect.height / 2});
  }, {passive: false});
  viewport.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    if (event.pointerType === 'touch') {
      touches.set(event.pointerId, {x:event.clientX,y:event.clientY});
      viewport.setPointerCapture(event.pointerId);
      if (touches.size === 2) {
        const [a,b] = [...touches.values()], rect = viewport.getBoundingClientRect();
        pinch = {distance:Math.hypot(a.x-b.x,a.y-b.y),zoom,x,y,anchor:{x:(a.x+b.x)/2-rect.left-rect.width/2,y:(a.y+b.y)/2-rect.top-rect.height/2}};
        pointer = null; suppressClick = true; event.preventDefault(); return;
      }
    }
    if (!viewport.classList.contains('can-pan')) return;
    pointer = {id: event.pointerId, startX: event.clientX, startY: event.clientY, x, y, moved: false, background: event.target === viewport};
    viewport.setPointerCapture(event.pointerId); viewport.classList.add('is-dragging'); event.preventDefault();
  });
  viewport.addEventListener('pointermove', event => {
    if (touches.has(event.pointerId)) touches.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if (pinch && touches.size === 2) {
      const [a,b] = [...touches.values()], rect = viewport.getBoundingClientRect();
      const next = clamp(pinch.zoom * Math.hypot(a.x-b.x,a.y-b.y) / Math.max(1,pinch.distance),.25,8), ratio = next / pinch.zoom;
      x = (a.x+b.x)/2-rect.left-rect.width/2 - (pinch.anchor.x-pinch.x)*ratio;
      y = (a.y+b.y)/2-rect.top-rect.height/2 - (pinch.anchor.y-pinch.y)*ratio;
      zoom = next; update(); return;
    }
    if (!pointer || pointer.id !== event.pointerId) return;
    const dx = event.clientX - pointer.startX, dy = event.clientY - pointer.startY;
    if (Math.hypot(dx, dy) > 3) pointer.moved = true;
    x = pointer.x + dx; y = pointer.y + dy; update();
  });
  function endDrag(event) {
    touches.delete(event.pointerId);
    if (pinch) {
      pinch = null; suppressClick = true;
      const remaining = [...touches.entries()][0];
      if (remaining) pointer = {id:remaining[0],startX:remaining[1].x,startY:remaining[1].y,x,y,moved:true,background:false};
    }
    if (!pointer || pointer.id !== event.pointerId) return;
    suppressClick = pointer.moved || !pointer.background;
    pointer = null; viewport.classList.remove('is-dragging');
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  }
  viewport.addEventListener('pointerup', endDrag);
  viewport.addEventListener('pointercancel', endDrag);
  viewport.addEventListener('lostpointercapture', endDrag);
  viewport.addEventListener('click', event => {
    if (!suppressClick && event.target === viewport) onBackdrop();
    suppressClick = false;
  });
  const observer = new ResizeObserver(update); observer.observe(viewport);
  return {
    root, viewport, frame, status,
    get scale() { return fit * zoom; },
    setContent(content, w, h) { frame.replaceChildren(content); width = w; height = h; reset(); },
    destroy() { observer.disconnect(); },
  };
}

export function createImageViewer(host, {src, title, onBackdrop}) {
  const view = createViewport(host, {onBackdrop});
  const image = new Image(); image.alt = title; image.draggable = false;
  let destroyed = false;
  view.status.textContent = '图片加载中…';
  image.onload = () => {
    if (destroyed) return;
    view.setContent(image, image.naturalWidth, image.naturalHeight); view.status.textContent = '';
  };
  image.onerror = () => { if (!destroyed) view.status.textContent = '图片加载失败，请关闭后重试。'; };
  image.src = src;
  return {destroy() { destroyed = true; image.onload = image.onerror = null; view.destroy(); }};
}

const pdfDocuments = new Map();
let pdfLibrary;
function acquirePDF(href) {
  let entry = pdfDocuments.get(href);
  if (!entry) {
    entry = {refs: 0, task: null};
    pdfLibrary ||= import(sitePath('/static/vendor/pdfjs/pdf.min.mjs')).then(lib => {
      lib.GlobalWorkerOptions.workerSrc = sitePath('/static/vendor/pdfjs/pdf.worker.min.mjs'); return lib;
    }).catch(error => { pdfLibrary = null; throw error; });
    entry.promise = pdfLibrary.then(lib => {
      if (!entry.refs) throw new Error('Viewer closed');
      entry.task = lib.getDocument({url: href, disableAutoFetch: true, disableStream: true, rangeChunkSize: 262144,
        cMapUrl: sitePath('/static/vendor/pdfjs/cmaps/'), cMapPacked: true, standardFontDataUrl: sitePath('/static/vendor/pdfjs/standard_fonts/'),
        wasmUrl: sitePath('/static/vendor/pdfjs/wasm/'), iccUrl: sitePath('/static/vendor/pdfjs/iccs/')});
      return entry.task.promise;
    }).catch(error => {
      if (pdfDocuments.get(href) === entry) pdfDocuments.delete(href);
      throw error;
    });
    pdfDocuments.set(href, entry);
  }
  entry.refs++;
  return {promise: entry.promise, release() {
    if (--entry.refs === 0) {
      if (pdfDocuments.get(href) === entry) pdfDocuments.delete(href);
      entry.task?.destroy().catch(() => {});
    }
  }};
}

export function createPDFViewer(host, {href, title, initialPage = 1}) {
  host.innerHTML = `<div class="asset-viewer asset-pdf-viewer" aria-busy="true">
    <div class="asset-pdf-scroll" tabindex="0" aria-label="文档预览，上下滚动浏览页面"><div class="asset-pdf-pages"></div><div class="asset-viewer-status" role="status">文档加载中…</div></div>
    <div class="asset-viewer-toolbar" aria-label="预览工具">
      <div class="asset-page-controls">${button('page-previous','上一页','previous')}<label><input type="number" min="1" value="1" aria-label="页码" disabled><span class="asset-page-total">/ —</span></label>${button('page-next','下一页','next')}</div>
      <div class="asset-zoom-controls">${button('zoom-out','缩小','minus')}<span class="asset-zoom-value" title="相对适应窗口的比例">100%</span>${button('zoom-in','放大','plus')}<button type="button" class="pill-btn grey" data-viewer-action="fit">适应窗口</button></div>
    </div></div>`;
  const root = host.firstElementChild, scroller = root.querySelector('.asset-pdf-scroll'), pages = root.querySelector('.asset-pdf-pages');
  const status = root.querySelector('.asset-viewer-status'), input = root.querySelector('input');
  const previous = root.querySelector('[data-viewer-action="page-previous"]'), next = root.querySelector('[data-viewer-action="page-next"]');
  const zoomIn = root.querySelector('[data-viewer-action="zoom-in"]'), zoomOut = root.querySelector('[data-viewer-action="zoom-out"]');
  let lease = acquirePDF(href), pdf, records = [], destroyed = false, zoom = 1, fit = 1, pageNumber = initialPage, frameRequest = 0, pointer;
  let lastWidth = 0, lastHeight = 0;
  previous.disabled = next.disabled = true;
  function updateControls() {
    if (!pdf) return;
    if (window.document.activeElement !== input) input.value = pageNumber;
    input.disabled = false; input.max = pdf.numPages;
    root.querySelector('.asset-page-total').textContent = `/ ${pdf.numPages}`;
    previous.disabled = pageNumber <= 1; next.disabled = pageNumber >= pdf.numPages;
    root.querySelector('.asset-zoom-value').textContent = `${Math.round(zoom * 100)}%`;
    zoomOut.disabled = zoom <= .25; zoomIn.disabled = zoom >= 8;
    root.dataset.page = pageNumber;
  }
  function layout() {
    if (!records.length) return;
    const first = records[0];
    fit = Math.max(.01, Math.min((scroller.clientWidth - 48) / first.width, (scroller.clientHeight - 48) / first.height, 1));
    for (const record of records) {
      record.element.style.width = `${record.width * fit * zoom}px`;
      record.element.style.height = `${record.height * fit * zoom}px`;
    }
    scroller.classList.toggle('can-pan', zoom > 1);
    updateControls(); schedule();
  }
  function setZoom(value, reset = false) {
    if (!records.length) return;
    const current = records[pageNumber - 1], oldScale = fit * zoom;
    const ratio = (scroller.scrollTop + scroller.clientHeight / 2 - current.element.offsetTop) / current.element.offsetHeight;
    const oldLeft = scroller.scrollLeft;
    zoom = clamp(value, .25, 8); layout();
    scroller.scrollTop = reset ? current.element.offsetTop - 24 : current.element.offsetTop + ratio * current.element.offsetHeight - scroller.clientHeight / 2;
    scroller.scrollLeft = reset ? 0 : (oldLeft + scroller.clientWidth / 2) * fit * zoom / oldScale - scroller.clientWidth / 2;
  }
  function goToPage(number) {
    if (!pdf) return;
    pageNumber = clamp(Math.round(Number(number)) || 1, 1, pdf.numPages);
    input.value = pageNumber;
    scroller.scrollTop = records[pageNumber - 1].element.offsetTop - 24;
    updateControls(); schedule();
  }
  function schedule() {
    if (!destroyed && !frameRequest) frameRequest = requestAnimationFrame(inspectVisible);
  }
  function inspectVisible() {
    frameRequest = 0;
    if (destroyed || !records.length) return;
    const top = scroller.scrollTop, bottom = top + scroller.clientHeight, middle = (top + bottom) / 2;
    let closest = Infinity;
    for (const record of records) {
      const start = record.element.offsetTop, end = start + record.element.offsetHeight;
      const distance = Math.abs((start + end) / 2 - middle);
      if (distance < closest) { closest = distance; pageNumber = record.number; }
      record.active = end > top - scroller.clientHeight / 2 && start < bottom + scroller.clientHeight / 2;
      if (record.active) render(record);
      else if (record.scale) {
        record.token++; record.task?.cancel(); record.task = null; record.scale = 0;
        record.element.replaceChildren(); delete record.element.dataset.rendered;
        record.page?.cleanup();
      }
    }
    updateControls();
    root.setAttribute('aria-busy', String(records[pageNumber - 1].element.dataset.rendered !== 'true'));
  }
  async function render(record) {
    const scale = fit * zoom;
    if (Math.abs(record.scale - scale) < .001) return;
    record.scale = scale; record.task?.cancel();
    const token = ++record.token;
    try {
      record.pagePromise ||= pdf.getPage(record.number);
      const page = await record.pagePromise;
      if (destroyed || token !== record.token || !record.active) return;
      record.page = page;
      const base = page.getViewport({scale: 1});
      if (Math.abs(record.width - base.width) > .01 || Math.abs(record.height - base.height) > .01) {
        record.width = base.width; record.height = base.height; layout();
      }
      const outputScale = Math.min(scale * (window.devicePixelRatio || 1), Math.sqrt(16000000 / (base.width * base.height)));
      const viewport = page.getViewport({scale: outputScale}), canvas = window.document.createElement('canvas');
      canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
      canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', `${title}，第 ${record.number} 页`);
      const task = page.render({canvasContext: canvas.getContext('2d'), viewport}); record.task = task;
      await task.promise;
      if (destroyed || token !== record.token) return;
      record.task = null; record.element.replaceChildren(canvas); record.element.dataset.rendered = 'true';
      if (record.number === pageNumber) root.setAttribute('aria-busy', 'false');
    } catch (error) {
      if (destroyed || token !== record.token || error.name === 'RenderingCancelledException') return;
      record.task = null; record.pagePromise = null;
      const retry = window.document.createElement('button'); retry.type = 'button'; retry.className = 'pill-btn shadow asset-page-retry'; retry.textContent = '加载失败，重试';
      retry.onclick = () => { record.scale = 0; render(record); };
      record.element.replaceChildren(retry);
      root.setAttribute('aria-busy', 'false');
    }
  }
  async function loadDocument() {
    try {
      const loaded = await lease.promise;
      if (destroyed) return;
      pdf = loaded;
      const first = await pdf.getPage(1);
      if (destroyed) return;
      const base = first.getViewport({scale: 1});
      records = Array.from({length: pdf.numPages}, (_, index) => {
        const element = window.document.createElement('div'); element.className = 'asset-pdf-page'; element.dataset.pageNumber = index + 1;
        return {number: index + 1, element, width: base.width, height: base.height, token: 0, scale: 0, active: false};
      });
      records[0].pagePromise = Promise.resolve(first);
      pages.replaceChildren(...records.map(record => record.element)); status.textContent = '';
      layout(); goToPage(initialPage);
    } catch (error) {
      if (destroyed) return;
      root.setAttribute('aria-busy', 'false'); status.textContent = '文档加载失败。';
      const retry = window.document.createElement('button'); retry.type = 'button'; retry.className = 'pill-btn shadow'; retry.textContent = '重试';
      retry.onclick = () => { lease.release(); lease = acquirePDF(href); status.textContent = '文档加载中…'; loadDocument(); };
      status.append(retry);
    }
  }
  // Leave wheel and touch scrolling native: PDF pages flow vertically at every zoom level.
  scroller.addEventListener('scroll', schedule, {passive: true});
  scroller.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.pointerType === 'touch' || zoom <= 1 || event.target.closest('button')) return;
    pointer = {id: event.pointerId, x: event.clientX, y: event.clientY, left: scroller.scrollLeft, top: scroller.scrollTop};
    scroller.setPointerCapture(event.pointerId); scroller.classList.add('is-dragging'); event.preventDefault();
  });
  scroller.addEventListener('pointermove', event => {
    if (!pointer || pointer.id !== event.pointerId) return;
    scroller.scrollLeft = pointer.left - event.clientX + pointer.x; scroller.scrollTop = pointer.top - event.clientY + pointer.y;
  });
  function endDrag(event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    pointer = null; scroller.classList.remove('is-dragging');
    if (scroller.hasPointerCapture(event.pointerId)) scroller.releasePointerCapture(event.pointerId);
  }
  scroller.addEventListener('pointerup', endDrag); scroller.addEventListener('pointercancel', endDrag); scroller.addEventListener('lostpointercapture', endDrag);
  previous.onclick = () => goToPage(pageNumber - 1); next.onclick = () => goToPage(pageNumber + 1);
  input.onchange = () => goToPage(input.value);
  input.onkeydown = event => { if (event.key === 'Enter') { goToPage(input.value); scroller.focus({preventScroll:true}); } };
  zoomOut.onclick = () => setZoom(zoom / 1.25); zoomIn.onclick = () => setZoom(zoom * 1.25);
  root.querySelector('[data-viewer-action="fit"]').onclick = () => setZoom(1, true);
  root.addEventListener('keydown', event => {
    if (event.target.matches('input') || event.ctrlKey || event.metaKey || event.altKey) return;
    if (['ArrowLeft','ArrowRight','+','=','-','0'].includes(event.key)) {
      event.preventDefault(); event.stopPropagation();
      if (event.key.startsWith('Arrow')) goToPage(pageNumber + (event.key === 'ArrowLeft' ? -1 : 1));
      else if (event.key === '0') setZoom(1, true); else setZoom(zoom * (event.key === '-' ? .8 : 1.25));
    }
  });
  const observer = new ResizeObserver(() => {
    if (lastWidth === scroller.clientWidth && lastHeight === scroller.clientHeight) return;
    lastWidth = scroller.clientWidth; lastHeight = scroller.clientHeight;
    layout(); if (pdf) goToPage(pageNumber);
  });
  observer.observe(scroller); loadDocument();
  return {get pageNumber() { return pageNumber; }, destroy() {
    if (destroyed) return;
    destroyed = true; cancelAnimationFrame(frameRequest); observer.disconnect();
    for (const record of records) { record.token++; record.task?.cancel(); }
    lease.release();
  }};
}
