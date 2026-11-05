const {icon} = window.VisionSite;
const {path: sitePath} = window.VisionSite;
const showcaseURL = 'https://app.air.inc/a/mf27a2a2e';

// Directories within the one shared showcase. Air hosts the board covers and files.
const boards = [
  ['品牌资产', '公司介绍、品牌视觉与合作品牌资料', '8348ff0f-3516-4047-a183-f6d614e3e387', '6469d16b-0041-4d34-a28d-d07627147b68'],
  ['产品系列', '按产品查找素材与渲染图', '8b784fe4-2473-4949-a8a7-062c800c46db', 'f9619ac3-4a5b-4a2f-a9a4-b14d8c07a6c5'],
  ['市场营销渠道', '零售渠道使用的设计素材', '7b21d43b-c197-423a-827d-0fc1f722221c', 'bbeebd30-986a-4da2-af22-7000f6ecc518'],
];

export function renderDesignAssets(host, {copy, notify}) {
  host.innerHTML = `<header class="head"><h1>设计资产</h1><span class="sub">设计团队在 Air 维护的素材库</span></header>
    <article class="design-showcase" aria-labelledby="designShowcaseTitle">
      <a class="showcase-cover" href="${showcaseURL}" target="_blank" rel="noopener noreferrer" aria-label="在 Air 打开 viaim 设计资源包">
        <img src="${sitePath('/static/assets/viaim-design-cover.webp')}" width="4746" height="840" alt="viaim · We Aim to Explore">
      </a>
      <div class="showcase-body">
        <div class="showcase-info"><h2 id="designShowcaseTitle">viaim 设计资源包</h2>
          <p><strong>含新品 · 谨慎公开</strong><span>分享前请确认接收范围。</span></p>
        </div>
        <div class="showcase-actions">
          <a class="pill-btn dark" href="${showcaseURL}" target="_blank" rel="noopener noreferrer">打开 Air ${icon('external')}</a>
          <button type="button" class="pill-btn shadow" data-copy-showcase>复制链接</button>
        </div>
      </div>
      <nav class="showcase-directory" aria-labelledby="designDirectoryTitle">
        <h3 id="designDirectoryTitle">资源目录</h3>
        <div class="showcase-boards">${boards.map(([name, description, board, cover]) => `
          <a class="showcase-board" href="${showcaseURL}/b/${board}" target="_blank" rel="noopener noreferrer">
            <span class="board-photo">
              ${icon('folder')}
              <img alt="" src="https://air-prod.imgix.net/${cover}.jpg?w=768&amp;h=432&amp;fit=crop&amp;crop=faces&amp;fm=webp" width="768" height="432" referrerpolicy="no-referrer">
            </span>
            <span class="board-title">${name}<span aria-hidden="true">${icon('external')}</span></span>
            <span class="board-caption">${description}</span>
          </a>`).join('')}</div>
      </nav>
    </article>`;
  for (const image of host.querySelectorAll('.board-photo img')) {
    image.onerror = () => { image.hidden = true; };
    if (image.complete && !image.naturalWidth) image.hidden = true;
  }
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
      card.querySelector('.showcase-body').after(input);
    }
    input.focus(); input.select();
    notify('请复制选中的分享链接');
  };
}
