/* Original-site players are the fallback when a source stream cannot load. */
let twitter;
function twitterWidgets() {
  if (window.twttr?.widgets) return Promise.resolve(window.twttr.widgets);
  return twitter ||= new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = 'https://platform.twitter.com/widgets.js';
    const timer = setTimeout(() => reject(new Error('Player unavailable')), 15000);
    script.onload = () => window.twttr.ready(() => { clearTimeout(timer); resolve(window.twttr.widgets); });
    script.onerror = () => { clearTimeout(timer); reject(new Error('Player unavailable')); };
    document.head.append(script);
  }).catch(error => { twitter = null; throw error; });
}

export function mountOnlineVideo(host, source, title) {
  let disposed = false;
  const player = document.createElement('div'), status = document.createElement('p'), link = document.createElement('a');
  host.classList.add('online-video');
  status.textContent = '正在加载视频…'; status.setAttribute('role','status');
  link.textContent = '查看原片'; link.href = source; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.className = 'pill-btn shadow';
  host.replaceChildren(player, status, link);
  const url = new URL(source), id = url.pathname.match(/\/status\/(\d+)/)?.[1];
  (async () => {
    try {
      if (['x.com','www.x.com','twitter.com','www.twitter.com','mobile.twitter.com'].includes(url.hostname) && id) {
        const widgets = await twitterWidgets();
        if (disposed) return;
        const result = await widgets.createVideo(id, player, {dnt:true,lang:'zh-cn',width:Math.round(host.clientWidth)});
        if (!result) throw new Error('Video unavailable');
      } else {
        let src;
        if (['youtube.com','www.youtube.com','youtu.be'].includes(url.hostname)) {
          const key = url.searchParams.get('v') || url.pathname.slice(1);
          if (/^[\w-]{11}$/.test(key)) src = `https://www.youtube.com/embed/${key}?playsinline=1&mute=1`;
        } else if (['vimeo.com','player.vimeo.com'].includes(url.hostname)) {
          const key = url.pathname.match(/^\/(?:video\/)?(\d+)\/?$/)?.[1];
          if (key) src = `https://player.vimeo.com/video/${key}?muted=1&playsinline=1&dnt=1`;
        }
        if (!src) throw new Error('Unsupported player');
        const frame = document.createElement('iframe'); frame.title = title;
        frame.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture'; frame.allowFullscreen = true;
        frame.referrerPolicy = 'strict-origin-when-cross-origin'; frame.src = src; player.append(frame);
      }
      if (!disposed) status.hidden = true;
    } catch { if (!disposed) status.textContent = '暂时无法播放，请查看原片'; }
  })();
  return () => { disposed = true; host.replaceChildren(); };
}
