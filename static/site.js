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
  window.VisionSite = Object.freeze({path, routePath, icon, videoPlayer, releaseVideo, staticMode: config.staticMode === true});
})();
