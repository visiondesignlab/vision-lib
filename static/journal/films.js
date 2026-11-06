const {icon} = window.VisionSite;
const scripts = new Map();
const initialVolume = 0.5;

// Third-party APIs are loaded only when a film comes into view or the reader chooses to play.
function sdk(name) {
  if (scripts.has(name)) return scripts.get(name);
  const youtube = name === 'youtube';
  const task = new Promise((resolve, reject) => {
    const ready = () => youtube ? window.YT?.Player : window.Vimeo?.Player;
    if (ready()) return resolve(ready());
    const script = document.createElement('script');
    script.src = youtube ? 'https://www.youtube.com/iframe_api' : 'https://player.vimeo.com/api/player.js';
    const timer = setTimeout(() => reject(new Error('播放器未就绪')), 12000);
    const finish = () => { clearTimeout(timer); ready() ? resolve(ready()) : reject(new Error('播放器未就绪')); };
    if (youtube) {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { finish(); previous?.(); };
    } else script.onload = finish;
    script.onerror = () => { clearTimeout(timer); reject(new Error('播放器未加载')); };
    document.head.append(script);
  }).catch(error => { scripts.delete(name); throw error; });
  scripts.set(name, task);
  return task;
}

function describe(url) {
  const u = new URL(url);
  if (['www.youtube.com','youtu.be'].includes(u.hostname)) {
    const id = u.searchParams.get('v') || u.pathname.slice(1);
    if (!/^[\w-]{11}$/.test(id)) return;
    return {kind:'youtube',id};
  }
  if (['vimeo.com','player.vimeo.com'].includes(u.hostname)) {
    const id = u.pathname.match(/^\/(?:video\/)?(\d+)\/?$/)?.[1];
    if (id) return {kind:'vimeo',id};
  }
  if (u.hostname === 'framerate.tv' && /^\/embed\/[\w-]+$/.test(u.pathname)) {
    u.searchParams.set('autoplay','0'); u.searchParams.set('muted','0');
    return {kind:'framerate',url:u.href};
  }
}

function mountFilm(figure, signal) {
  const url = figure.dataset.filmSource, film = describe(url), poster = figure.querySelector('img');
  if (!film || !poster) return;
  const region = document.createElement('div');
  region.className = 'journal-film';
  poster.before(region); region.append(poster);
  const title = poster.alt || '产品动态视频';
  let active = null, failed = false, visible = false;
  const status = document.createElement('span');
  status.className = 'journal-film-status'; status.hidden = true;
  const play = document.createElement('button');
  play.type = 'button'; play.className = 'pill-btn dark journal-film-play';
  play.textContent = '播放视频'; region.append(play, status);
  const source = document.createElement('a');
  source.href = film.kind === 'vimeo' ? 'https://vimeo.com/' + film.id : url;
  source.target = '_blank'; source.rel = 'noopener noreferrer';
  source.className = 'journal-film-source'; source.innerHTML = '查看原片 ' + icon('external');
  figure.querySelector('figcaption')?.append(' ', source);
  function stop() {
    const old = active; active = null;
    if (old) {
      clearTimeout(old.timer);
      old.removeListener?.();
      old.mount.remove(); // Removing the frame stops its audio even if the provider is unresponsive.
      if (old.player?.destroy) Promise.resolve().then(()=>old.player.destroy()).catch(()=>{});
    }
    poster.hidden = false; play.hidden = failed;
    status.hidden = !failed;
  }
  function error() {
    failed = true; stop(); play.hidden = true;
    status.textContent = '暂时无法播放，请查看原片'; status.hidden = false;
  }
  async function start() {
    if (document.hidden || active || failed || signal.aborted) return;
    const mount = document.createElement('div'); mount.className = 'journal-film-player'; region.prepend(mount);
    const current = active = {mount};
    const live = () => active === current && !signal.aborted;
    const unveil = () => {
      if (!live()) return;
      clearTimeout(current.timer); poster.hidden = true; play.hidden = true; status.hidden = true;
    };
    const unavailable = () => { if (live()) error(); };
    function embed(src) {
      const frame = document.createElement('iframe');
      frame.title = title; frame.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture'; frame.allowFullscreen = true;
      // Providers use the embedding site's origin to check playback permissions.
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      frame.src = src;
      mount.append(frame);
      return frame;
    }
    play.hidden = true; status.textContent = '正在加载视频…'; status.hidden = false;
    current.timer = setTimeout(unavailable,16000);
    try {
      if (film.kind === 'framerate') {
        const frame = embed(film.url);
        const origin = new URL(film.url).origin;
        const send = (method, value) => frame.contentWindow.postMessage(
          JSON.stringify({context:'player.js', version:'1.0', method, value}), origin);
        // Framerate uses the Player.js bridge and may announce readiness more than once.
        function onReady(event) {
          if (event.origin !== origin || event.source !== frame.contentWindow || !live()) return;
          let message = event.data;
          if (typeof message === 'string') {
            try { message = JSON.parse(message); } catch { return; }
          }
          if (message?.context !== 'player.js' || message.event !== 'ready') return;
          current.removeListener();
          send('setVolume', initialVolume * 100);
          send('unmute');
          send('play');
          unveil();
        }
        current.removeListener = () => window.removeEventListener('message', onReady);
        window.addEventListener('message', onReady);
        frame.onload = () => { if (live()) send('addEventListener', 'ready'); };
      } else if (film.kind === 'youtube') {
        const Player = await sdk('youtube');
        if (!live()) return;
        const params = new URLSearchParams({enablejsapi:'1',origin:location.origin,playsinline:'1',autoplay:'0',rel:'0'});
        const frame = embed('https://www.youtube.com/embed/' + film.id + '?' + params);
        current.player = new Player(frame, {
          events:{onReady:e=>{ if (live()) { e.target.setVolume(initialVolume * 100); e.target.unMute(); e.target.playVideo(); unveil(); } },
            onError:unavailable, onAutoplayBlocked:unveil}});
      } else {
        const Player = await sdk('vimeo');
        if (!live()) return;
        const frame = embed('https://player.vimeo.com/video/' + film.id + '?muted=0&autoplay=0&playsinline=1&dnt=1');
        const player = current.player = new Player(frame);
        player.on('error', event => {
          if (event?.name === 'NotAllowedError' || event?.method === 'setVolume') return;
          unavailable();
        });
        await player.ready();
        if (!live()) return;
        unveil();
        await player.setVolume(initialVolume).catch(()=>{}); // Some mobile players use hardware volume.
        if (!live()) return;
        await player.setMuted(false);
        if (live()) await player.play().catch(e=>{ if (e.name !== 'NotAllowedError') unavailable(); });
      }
    } catch { unavailable(); }
  }
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  function sync() {
    if (!visible || document.hidden) stop();
    else if (!reduced.matches) start();
  }
  const observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting && entry.intersectionRatio >= 0.5; sync();
  }, {threshold:[0,0.5]});
  observer.observe(region);
  play.addEventListener('click', start, {signal});
  document.addEventListener('visibilitychange', sync, {signal});
  window.addEventListener('pagehide', stop, {signal});
  signal.addEventListener('abort',()=>{ observer.disconnect(); stop(); }, {once:true});
}

export function mountJournalFilms(view, signal) {
  for (const figure of view.querySelectorAll('figure[data-film-source]')) mountFilm(figure, signal);
}
