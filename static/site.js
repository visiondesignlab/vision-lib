/* Shared paths for the local server and GitHub Pages project sites. */
(() => {
  const config = window.VISION_CONFIG || {};
  const base = (config.basePath || '').replace(/\/$/, '');
  function path(value) {
    if (!base || typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return value;
    if (value === base || value.startsWith(base + '/') || value.startsWith(base + '?')) return value;
    return base + value;
  }
  function routePath(value = location.pathname) {
    if (base && (value === base || value.startsWith(base + '/'))) value = value.slice(base.length);
    return value.replace(/\/$/, '') || '/';
  }
  function icon(name) {
    return `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="${path('/static/icons/hugeicons.svg')}#${name}"></use></svg>`;
  }
  // actionsHTML is trusted UI markup authored by the caller, never content from a record.
  function emptyState({title, description, icon: symbol = 'inbox', actionsHTML = '', compact = false, busy = false}) {
    const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character]));
    return `<div class="empty-state${compact ? ' empty-state--compact' : ''}" role="status"${busy ? ' aria-busy="true"' : ''}>
      <span class="empty-state-icon" aria-hidden="true">${icon(symbol)}</span>
      <h2 class="empty-state-title">${escape(title)}</h2>
      <p class="empty-state-description">${escape(description)}</p>
      ${actionsHTML ? `<div class="empty-state-actions">${actionsHTML}</div>` : ''}
    </div>`;
  }
  function videoPlayer(src, poster, {detail=false}={}) {
    // Set media attributes inside an inert template. Only the mounted player can load or play.
    const template=document.createElement('template');
    template.innerHTML='<div class="video-surface"><video controls loop playsinline></video></div>';
    const video=template.content.querySelector('video');
    video.setAttribute('src',src);
    video.setAttribute('poster',poster || path('/static/cms-placeholder.svg'));
    if(!detail) {
      video.setAttribute('autoplay','');
      video.setAttribute('muted','');
    }
    return template.innerHTML;
  }
  function releaseVideo(video) {
    video.muted=true;
    video.pause();
    video.loop=false;
    video.autoplay=false;
    video.removeAttribute('src');
    video.load();
  }
  window.VisionSite = Object.freeze({path, routePath, icon, emptyState, videoPlayer, releaseVideo, staticMode: config.staticMode === true});
})();
