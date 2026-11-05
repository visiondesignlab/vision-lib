const {path: sitePath} = window.VisionSite;
const showcaseURL = 'https://app.air.inc/a/mf27a2a2e';

export function renderDesignAssets(host, {copy, notify}) {
  host.innerHTML = `<header class="head"><h1>设计资产</h1><span class="sub">设计团队在 Air 维护的品牌与产品素材</span></header>
    <article class="design-showcase" aria-labelledby="designShowcaseTitle">
      <a class="showcase-cover" href="${showcaseURL}" target="_blank" rel="noopener noreferrer" aria-label="在 Air 打开 viaim 设计资源包">
        <img src="${sitePath('/static/assets/air-showcase-banner.webp')}" width="1280" height="115" alt="viaim · We Aim to Explore">
      </a>
      <div class="showcase-body">
        <div class="showcase-info"><h2 id="designShowcaseTitle">viaim 设计资源包</h2>
          <p><strong>含新品 · 谨慎公开</strong><span>请确认接收范围后再分享。</span></p>
        </div>
        <div class="showcase-actions">
          <button type="button" class="pill-btn dark" data-copy-showcase>复制链接</button>
          <a class="pill-btn shadow" href="${showcaseURL}" target="_blank" rel="noopener noreferrer">打开 Air ↗</a>
        </div>
      </div>
    </article>`;
  const button = host.querySelector('[data-copy-showcase]');
  button.onclick = async () => {
    if (await copy(showcaseURL)) {
      notify('设计资源包链接已复制');
      return;
    }
    const card = button.closest('article');
    if (!card?.isConnected) return;
    let input = card.querySelector('input');
    if (!input) {
      input = document.createElement('input');
      input.className = 'showcase-share-url';
      input.setAttribute('aria-label', 'Air 分享链接');
      input.readOnly = true;
      input.value = showcaseURL;
      card.append(input);
    }
    input.focus(); input.select();
    notify('请复制选中的分享链接');
  };
}
