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
  function videoPlayer(src, poster) {
    const surface = document.createElement('div'), video = document.createElement('video');
    surface.className = 'video-surface';
    video.src = src; video.poster = poster || path('/static/cms-placeholder.svg');
    for (const attr of ['controls', 'autoplay', 'muted', 'loop', 'playsinline']) video.setAttribute(attr, '');
    surface.append(video);
    return surface.outerHTML;
  }
  window.VisionSite = Object.freeze({path, routePath, videoPlayer, staticMode: config.staticMode === true});
})();
