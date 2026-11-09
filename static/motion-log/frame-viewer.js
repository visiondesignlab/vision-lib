const {icon} = window.VisionSite;

export function mountFrameViewer(view, signal) {
  const links = [...view.querySelectorAll('.motion-shot-index a[data-motion-asset]')];
  if (!links.length) return;
  const frames = links.map(link => {
    link.removeAttribute('target');
    link.setAttribute('aria-haspopup', 'dialog');
    const cells = link.closest('tr').cells;
    return {link, src:link.href, shot:cells[0].textContent.trim(), time:cells[1].textContent.trim()};
  });
  const dialog = document.createElement('dialog');
  dialog.className = 'motion-frame-dialog';
  dialog.setAttribute('aria-labelledby', 'motion-frame-title');
  dialog.innerHTML = `<header class="motion-frame-header"><h2 id="motion-frame-title">代表帧</h2><button type="button" class="ibtn" data-frame-close aria-label="关闭代表帧预览" title="关闭（Esc）" autofocus>${icon('close')}</button></header>
    <div class="motion-frame-stage"><img alt="" hidden><p role="status">正在加载图片…</p></div>
    <footer class="motion-frame-footer"><button type="button" class="ibtn" data-frame-prev aria-label="上一张代表帧" title="上一张（←）">${icon('back')}</button><div><span class="motion-frame-caption"></span><small>← / → 切换 · Esc 关闭</small></div><button type="button" class="ibtn" data-frame-next aria-label="下一张代表帧" title="下一张（→）">${icon('forward')}</button></footer>`;
  view.append(dialog);
  const image = dialog.querySelector('img');
  const status = dialog.querySelector('[role="status"]');
  const previous = dialog.querySelector('[data-frame-prev]');
  const next = dialog.querySelector('[data-frame-next]');
  let index = 0, request = 0, trigger, savedOverflow;

  function show(nextIndex) {
    if (nextIndex < 0 || nextIndex >= frames.length) return;
    index = nextIndex;
    const frame = frames[index], current = ++request;
    dialog.querySelector('h2').textContent = `代表帧 ${index + 1} / ${frames.length}`;
    dialog.querySelector('.motion-frame-caption').textContent = `镜头 ${frame.shot} · ${frame.time}`;
    previous.disabled = index === 0;
    next.disabled = index === frames.length - 1;
    image.hidden = true;
    image.alt = `镜头 ${frame.shot}，${frame.time}，代表帧`;
    status.textContent = '正在加载图片…';
    status.hidden = false;
    const preload = new Image();
    preload.onload = () => {
      if (current !== request || signal.aborted || !dialog.open) return;
      dialog.style.setProperty('--motion-frame-ratio', `${preload.naturalWidth} / ${preload.naturalHeight}`);
      image.src = frame.src;
      image.hidden = false;
      status.hidden = true;
    };
    preload.onerror = () => {
      if (current !== request || signal.aborted || !dialog.open) return;
      status.textContent = '图片暂时无法加载，请稍后重试。';
    };
    preload.src = frame.src;
  }
  function restoreScroll() {
    if (savedOverflow !== undefined) {
      document.documentElement.style.overflow = savedOverflow;
      savedOverflow = undefined;
    }
  }
  function close() {
    ++request;
    dialog.close();
    restoreScroll();
    if (trigger?.isConnected) trigger.focus({preventScroll:true});
  }
  view.addEventListener('click', event => {
    const link = event.target.closest('.motion-shot-index a[data-motion-asset]');
    const nextIndex = links.indexOf(link);
    if (nextIndex < 0 || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    trigger = link;
    savedOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    dialog.showModal();
    show(nextIndex);
  }, {signal});
  dialog.querySelector('[data-frame-close]').addEventListener('click', close, {signal});
  previous.addEventListener('click', () => show(index - 1), {signal});
  next.addEventListener('click', () => show(index + 1), {signal});
  dialog.addEventListener('cancel', event => {event.preventDefault(); close();}, {signal});
  dialog.addEventListener('close', restoreScroll, {signal});
  dialog.addEventListener('click', event => {if (event.target === dialog) close();}, {signal});
  window.addEventListener('popstate', () => {if (dialog.open) close();}, {signal});
  document.addEventListener('keydown', event => {
    if (!dialog.open || event.defaultPrevented || event.isComposing || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const offset = {ArrowLeft:-1, ArrowRight:1}[event.key];
    if (offset) {event.preventDefault(); show(index + offset);}
  }, {signal});
  signal.addEventListener('abort', () => {++request; restoreScroll(); dialog.remove();}, {once:true});
}
