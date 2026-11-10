const {icon} = window.VisionSite;
/* Adapted from the local Assets 切图 tool; files stay in the browser. */
import "../vendor/jszip.min.js";

export function createImageSlicer() {
const root = document.createElement("div");
root.className = "image-slicer";
root.innerHTML = `
  <header class="head">
    <h1>图片切图</h1><span class="sub">为 Figma 与电商长图，轻松缩放与切片</span>
    <div class="right"><span class="tag">本地处理</span></div>
  </header>
  <div class="bar">
    <div class="chips" role="group" aria-label="裁切方式">
      <button type="button" class="chip on" data-mode="auto" aria-pressed="true">自动切片</button>
      <button type="button" class="chip" data-mode="manual" aria-pressed="false">定点裁切</button>
    </div>
    <span class="slicer-mode-hint" id="modeHint">按最大尺寸，自动分行分列</span>
    <select id="cutMode" hidden aria-label="裁切方式"><option value="auto">自动切片</option><option value="manual">定点裁切</option></select>
  </div>
  <div class="slicer-workspace">
    <section class="slicer-controls slicer-surface" aria-label="切图设置">
      <div class="slicer-section-title"><h2>图片</h2><span class="muted" id="fileCount">未选择</span></div>
      <label class="slicer-dropzone" id="dropzone">
        <input id="fileInput" type="file" accept="image/*" multiple aria-label="选择图片（可多选）">
        ${icon('upload')}
        <b id="filePrompt">点击选择，或拖入图片</b>
        <span>支持 PNG、JPG、WebP 等图片格式</span>
      </label>
      <ul id="fileList" class="slicer-file-list" aria-label="已选图片" hidden></ul>
      <div class="slicer-settings">
        <h2>输出设置</h2>
        <label class="field"><span>输出宽度 <span class="muted">· 可选</span></span><div class="slicer-input"><input id="targetWidth" type="number" min="1" step="1" placeholder="保留原图宽度" aria-describedby="resizeHint"><span>px</span></div></label>
        <p class="slicer-help" id="resizeHint">等比缩放，高度向下取整至整数像素。</p>
        <div class="slicer-field-pair">
          <label class="field"><span>切片最大宽度</span><div class="slicer-input"><input id="chunkWidth" type="number" min="1" step="1" value="4096"><span>px</span></div></label>
          <label class="field"><span>切片最大高度</span><div class="slicer-input"><input id="chunkHeight" type="number" min="1" step="1" value="4096"><span>px</span></div></label>
        </div>
        <p class="slicer-help">默认每张切片不超过 4096 × 4096 px。</p>
      </div>
      <div class="slicer-actions">
        <button id="sliceBtn" type="button" class="pill-btn dark">开始切图</button>
        <button id="loadPreviewBtn" type="button" class="pill-btn shadow" hidden>加载预览</button>
        <button id="clearBtn" type="button" class="pill-btn grey">清空</button>
      </div>
      <p class="slicer-help slicer-local-note">图片仅在浏览器中处理，无需上传。</p>
    </section>
    <div class="slicer-output">
      <section id="manualPanel" class="slicer-surface manual-panel" aria-labelledby="manualTitle" hidden>
        <div class="slicer-section-title"><h2 id="manualTitle" tabindex="-1">定点裁切</h2><button id="clearCutsBtn" type="button" class="pill-btn grey">清空标记</button></div>
        <p class="slicer-help">轻触或点击预览添加切线，也可输入精确 Y 坐标。超出最大高度时，会在本段最大高度处添加切线。</p>
        <div class="manual-tools">
          <label class="field" for="cutYInput">裁切位置 Y</label>
          <div class="slicer-input"><input id="cutYInput" type="number" min="1" step="1" placeholder="例如 1280"><span>px</span></div>
          <button id="addCutYBtn" type="button" class="pill-btn shadow">添加切线</button>
        </div>
        <div id="previewStatus" class="slicer-status" role="status" aria-live="polite">选择一张图片，点击“加载预览”。</div>
        <div class="preview-scroll" tabindex="0" role="region" aria-label="图片裁切预览，可滚动查看">
          <div id="previewFrame" class="preview-frame" hidden>
            <img id="previewImage" class="preview-image" alt="裁切预览" draggable="false">
            <div id="cutOverlay" class="cut-overlay"></div>
            <div id="knifeGuide" class="knife-guide" hidden><span id="knifeLabel" class="knife-label"></span></div>
          </div>
        </div>
        <div id="cutList" class="cut-list">尚未添加裁切点。</div>
        <div class="slicer-pane-actions">
          <button id="manualSliceBtn" type="button" class="pill-btn dark">开始切图</button>
          <button id="showResultsBtn" type="button" class="pill-btn shadow">查看结果</button>
        </div>
      </section>
      <section id="resultPanel" class="slicer-surface slicer-result-panel" aria-labelledby="resultTitle">
        <div class="slicer-section-title"><h2 id="resultTitle" tabindex="-1">处理结果 <span class="tag" id="sliceCount">0 张</span></h2><button id="downloadZipBtn" type="button" class="pill-btn shadow" disabled>下载全部 ZIP</button></div>
        <div id="status" class="slicer-status" role="status" aria-live="polite">选择图片并设置尺寸，点击“开始切图”。</div>
        <div class="slicer-results-scroll" tabindex="0" role="region" aria-label="切片处理结果，可滚动查看">
          <div id="resultEmpty" class="slicer-empty">
            ${VisionSite.emptyState({icon:'crop',title:'还没有切图结果',description:'选择图片并开始切图，切片预览与下载会显示在这里。'})}
          </div>
          <div id="results" class="results"></div>
        </div>
        <div id="resultActions" class="slicer-pane-actions" hidden><button id="showPreviewBtn" type="button" class="pill-btn shadow">返回裁切</button></div>
      </section>
    </div>
  </div>`;
const getElement = id => root.querySelector(`#${id}`);
const fileInput = getElement("fileInput");
const targetWidthInput = getElement("targetWidth");
const chunkWidthInput = getElement("chunkWidth");
const chunkHeightInput = getElement("chunkHeight");
const cutModeInput = getElement("cutMode");
const sliceBtn = getElement("sliceBtn");
const loadPreviewBtn = getElement("loadPreviewBtn");
const clearBtn = getElement("clearBtn");
const downloadZipBtn = getElement("downloadZipBtn");
const statusEl = getElement("status");
const resultsEl = getElement("results");
const manualPanel = getElement("manualPanel");
const previewStatusEl = getElement("previewStatus");
const previewFrame = getElement("previewFrame");
const previewImage = getElement("previewImage");
const cutOverlay = getElement("cutOverlay");
const knifeGuide = getElement("knifeGuide");
const knifeLabel = getElement("knifeLabel");
const cutList = getElement("cutList");
const cutYInput = getElement("cutYInput");
const addCutYBtn = getElement("addCutYBtn");
const clearCutsBtn = getElement("clearCutsBtn");
const resultPanel = getElement("resultPanel");
const resultsScroll = root.querySelector(".slicer-results-scroll");

function revealPanel(panel, heading) {
  // Do not move the page when both panes already fit side by side.
  const rect = panel.getBoundingClientRect();
  const header = document.querySelector(".mobile-header");
  const topInset = header ? header.getBoundingClientRect().height : 0;
  if (rect.top < topInset || rect.bottom > window.innerHeight) {
    panel.scrollIntoView({block: "start", behavior: "instant"});
  }
  getElement(heading).focus({preventScroll: true});
}
getElement("showResultsBtn").addEventListener("click", () => revealPanel(resultPanel, "resultTitle"));
getElement("showPreviewBtn").addEventListener("click", () => revealPanel(manualPanel, "manualTitle"));
getElement("manualSliceBtn").addEventListener("click", () => sliceBtn.click());

let busy = false;
const allSlices = [];
const filePreviewUrls = [];
function setBusy(value) {
  busy = value;
  root.setAttribute("aria-busy", String(value));
  root.querySelectorAll(".slicer-controls input, .slicer-controls button, [data-mode], .manual-tools input, .manual-tools button, #clearCutsBtn, #manualSliceBtn").forEach(el => el.disabled = value);
}
function syncResultSummary() {
  getElement("sliceCount").textContent = `${allSlices.length} 张`;
  getElement("resultEmpty").hidden = allSlices.length > 0;
}
function updateFileSummary() {
  const files = Array.from(fileInput.files || []);
  getElement("fileCount").textContent = files.length ? `${files.length} 张` : "未选择";
  getElement("filePrompt").textContent = files.length ? "点击更换，或拖入新图片" : "点击选择，或拖入图片";
  const list = getElement("fileList");
  list.replaceChildren();
  filePreviewUrls.forEach(url => URL.revokeObjectURL(url));
  filePreviewUrls.length = 0;
  files.forEach((file, index) => {
    const row = document.createElement("li");
    const thumbnail = document.createElement("img");
    const url = URL.createObjectURL(file);
    filePreviewUrls.push(url);
    thumbnail.src = url;
    thumbnail.alt = `${file.name} 预览`;
    thumbnail.className = "slicer-file-thumb";
    const info = document.createElement("div");
    info.className = "slicer-file-info";
    const name = document.createElement("span");
    name.className = "slicer-file-name";
    name.textContent = file.name; name.title = file.name;
    const size = document.createElement("span");
    size.className = "slicer-file-size";
    size.textContent = file.size >= 1024 * 1024 ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(file.size / 1024))} KB`;
    thumbnail.onload = () => { size.textContent = `${thumbnail.naturalWidth} × ${thumbnail.naturalHeight} px`; };
    thumbnail.onerror = () => { thumbnail.hidden = true; size.textContent = "图片预览不可用"; };
    info.append(name, size);
    const remove = document.createElement("button");
    remove.type = "button"; remove.className = "slicer-file-remove";
    remove.innerHTML = icon("close"); remove.title = "取消选择";
    remove.setAttribute("aria-label", `取消选择 ${file.name}`);
    remove.disabled = busy;
    remove.addEventListener("click", () => {
      if (busy) return;
      const transfer = new DataTransfer();
      Array.from(fileInput.files).forEach((selected, i) => { if (i !== index) transfer.items.add(selected); });
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event("change"));
      const buttons = list.querySelectorAll("button");
      (buttons[Math.min(index, buttons.length - 1)] || fileInput).focus({preventScroll: true});
    });
    row.append(thumbnail, info, remove);
    list.appendChild(row);
  });
  list.hidden = !files.length;
}
const objectUrls = [];
const manualCutState = {
  signature: "",
  previewUrl: "",
  width: 0,
  height: 0,
  outputWidth: 0,
  outputHeight: 0,
  resized: false,
  cuts: [],
};

function setStatus(text) {
  statusEl.textContent = text;
}

function resetView() {
  resultsEl.innerHTML = "";
  resultsScroll.scrollTop = 0;
  allSlices.length = 0;
  downloadZipBtn.disabled = true;
  for (const url of objectUrls) {
    URL.revokeObjectURL(url);
  }
  objectUrls.length = 0;
  syncResultSummary();
}

function resetManualCutState() {
  if (manualCutState.previewUrl) {
    URL.revokeObjectURL(manualCutState.previewUrl);
  }
  manualCutState.signature = "";
  manualCutState.previewUrl = "";
  manualCutState.width = 0;
  manualCutState.height = 0;
  manualCutState.outputWidth = 0;
  manualCutState.outputHeight = 0;
  manualCutState.resized = false;
  manualCutState.cuts = [];
  previewImage.removeAttribute("src");
  previewFrame.removeAttribute("style");
  previewFrame.hidden = true;
  hideKnifeGuide();
  cutOverlay.innerHTML = "";
  cutList.textContent = "尚未添加裁切点。";
  previewStatusEl.textContent = "切换到定点裁切后加载预览。";
}

function getFileExt(file) {
  const lowerName = file.name.toLowerCase();
  if (lowerName.endsWith(".png")) return { mime: "image/png", ext: "png" };
  if (lowerName.endsWith(".webp")) return { mime: "image/webp", ext: "webp" };
  return { mime: "image/jpeg", ext: "jpeg" };
}

function toBlob(canvas, mime) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("切片生成失败"));
        return;
      }
      resolve(blob);
    }, mime);
  });
}

async function loadBitmap(file) {
  if ("createImageBitmap" in window) {
    return createImageBitmap(file);
  }
  const url = URL.createObjectURL(file);
  objectUrls.push(url);
  const img = new Image();
  img.decoding = "async";
  img.src = url;
  await img.decode();
  return img;
}

async function readImageSize(file) {
  if ("createImageBitmap" in window) {
    const bitmap = await createImageBitmap(file);
    const size = { width: bitmap.width, height: bitmap.height };
    if ("close" in bitmap && typeof bitmap.close === "function") {
      bitmap.close();
    }
    return size;
  }

  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return { width: img.naturalWidth, height: img.naturalHeight };
  } finally {
    URL.revokeObjectURL(url);
  }
}

function formatSliceMode(layout) {
  const { rows, columns, manual } = layout;
  if (manual) {
    return columns > 1 ? `定点裁切 ${rows} 段，每段 ${columns} 列` : `定点裁切 ${rows} 段`;
  }
  if (rows > 1 && columns > 1) return `${columns} 列 x ${rows} 行宫格`;
  if (rows > 1) return `${rows} 行纵向切分`;
  if (columns > 1) return `${columns} 列横向切分`;
  return "无需切分";
}

function getTargetWidth() {
  const raw = targetWidthInput.value.trim();
  if (!raw) return null;
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : NaN;
}

function getOutputSize(width, height, targetWidth) {
  if (targetWidth === null) {
    return {
      outputWidth: width,
      outputHeight: height,
      resized: false,
    };
  }

  const scale = targetWidth / width;
  // 平台适配要求直接抹掉小数位，即使小数大于 0.5 也不四舍五入。
  const outputHeight = Math.floor(height * scale);
  if (outputHeight < 1) {
    throw new Error("缩放后高度小于 1px，请增大输出宽度。");
  }

  return {
    outputWidth: targetWidth,
    outputHeight,
    resized: true,
  };
}

function getPreviewSignature(file, targetWidth) {
  return [
    file.name,
    file.size,
    file.lastModified,
    targetWidth === null ? "original" : targetWidth,
  ].join(":");
}

function setPreviewStatus(text) {
  previewStatusEl.textContent = text;
}

function getChunkHeightLimit() {
  const value = Number(chunkHeightInput.value);
  return Number.isInteger(value) && value > 0 ? value : NaN;
}

function snapCutY(y) {
  if (!manualCutState.outputHeight) return null;
  const snappedY = Math.round(y);
  return Math.max(1, Math.min(manualCutState.outputHeight - 1, snappedY));
}

function getPointerCutY(event) {
  if (!manualCutState.outputHeight) return null;

  const rect = cutOverlay.getBoundingClientRect();
  if (!rect.height) return null;

  const ratio = (event.clientY - rect.top) / rect.height;
  return snapCutY(ratio * manualCutState.outputHeight);
}

function getManualCutContext(y) {
  const cutsBeforeY = getSortedCuts(
    manualCutState.cuts.filter((cut) => cut < y),
    manualCutState.outputHeight
  );
  const previousCut = cutsBeforeY.length ? cutsBeforeY[cutsBeforeY.length - 1] : 0;
  const relativeY = y - previousCut;
  const maxHeight = getChunkHeightLimit();
  return {
    previousCut,
    relativeY,
    maxHeight,
    exceedsMaxHeight: Number.isInteger(maxHeight) && relativeY > maxHeight,
  };
}

function formatCutContext(y) {
  const context = getManualCutContext(y);
  const relativeText = Number.isInteger(context.maxHeight)
    ? `当前切图内 ${context.relativeY}/${context.maxHeight}px`
    : `当前切图内 ${context.relativeY}px`;
  return {
    ...context,
    text: `全图 Y ${y}px · ${relativeText}${
      context.exceedsMaxHeight ? " · 超出最大高度" : ""
    }`,
  };
}

function getPointerCutTarget(y) {
  const context = getManualCutContext(y);
  return context.exceedsMaxHeight ? context.previousCut + context.maxHeight : y;
}

function showKnifeGuide(y) {
  if (!manualCutState.outputHeight) return;
  const cut = getPointerCutTarget(y);
  const context = formatCutContext(cut);

  knifeGuide.style.top = `${cut / manualCutState.outputHeight * 100}%`;
  knifeLabel.textContent = context.text + (cut !== y ? " · 已吸附最大高度" : "");
  knifeGuide.classList.toggle("is-invalid", Number.isNaN(context.maxHeight));
  knifeGuide.hidden = false;
}

function hideKnifeGuide() {
  knifeGuide.hidden = true;
}

function getSortedCuts(cuts, outputHeight) {
  return Array.from(
    new Set(cuts.filter((cut) => Number.isInteger(cut) && cut > 0 && cut < outputHeight))
  ).sort((a, b) => a - b);
}

function removeManualCut(y) {
  manualCutState.cuts = manualCutState.cuts.filter((cut) => cut !== y);
  renderManualCuts();
}

function addManualCut(y) {
  if (!manualCutState.outputHeight) {
    setPreviewStatus("请先加载预览。");
    return false;
  }

  const cut = snapCutY(y);
  if (cut === null) {
    setPreviewStatus("请先加载预览。");
    return false;
  }
  if (cut <= 0 || cut >= manualCutState.outputHeight) {
    setPreviewStatus(`裁切坐标必须在 1 到 ${manualCutState.outputHeight - 1}px 之间。`);
    return false;
  }
  if (manualCutState.cuts.includes(cut)) {
    setPreviewStatus(`Y ${cut}px 已存在裁切标记。`);
    return false;
  }

  const context = formatCutContext(cut);
  if (Number.isNaN(context.maxHeight)) {
    setPreviewStatus("切片最大高度必须是大于 0 的整数。");
    return false;
  }
  if (context.exceedsMaxHeight) {
    showKnifeGuide(cut);
    setPreviewStatus(
      `不能添加：当前切图高度 ${context.relativeY}px，超过最大高度 ${context.maxHeight}px。`
    );
    return false;
  }

  manualCutState.cuts = getSortedCuts(
    [...manualCutState.cuts, cut],
    manualCutState.outputHeight
  );
  renderManualCuts();
  return true;
}

function renderManualCuts() {
  cutOverlay.innerHTML = "";
  cutList.innerHTML = "";

  if (!manualCutState.outputHeight) {
    cutList.textContent = "尚未添加裁切点。";
    setPreviewStatus("请先加载预览。");
    return;
  }

  if (!manualCutState.cuts.length) {
    cutList.textContent = "尚未添加裁切点。";
  }

  for (const cut of manualCutState.cuts) {
    const context = formatCutContext(cut);

    const line = document.createElement("div");
    line.className = "cut-line";
    line.style.top = `${cut / manualCutState.outputHeight * 100}%`;
    line.classList.toggle("is-invalid", context.exceedsMaxHeight);

    const label = document.createElement("span");
    label.className = "cut-label";
    label.classList.toggle("is-invalid", context.exceedsMaxHeight);

    const labelText = document.createElement("span");
    labelText.textContent = context.text;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "cut-remove";
    removeBtn.innerHTML = icon("close");
    removeBtn.setAttribute("aria-label", `删除 Y ${cut}px 切线`);
    removeBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      removeManualCut(cut);
    });
    label.append(labelText, removeBtn);
    line.appendChild(label);
    cutOverlay.appendChild(line);

    const chip = document.createElement("span");
    chip.className = "cut-chip";
    chip.classList.toggle("is-invalid", context.exceedsMaxHeight);

    const chipText = document.createElement("span");
    chipText.textContent = context.text;

    const chipRemove = document.createElement("button");
    chipRemove.type = "button";
    chipRemove.className = "chip-remove";
    chipRemove.innerHTML = icon("close");
    chipRemove.setAttribute("aria-label", `删除 Y ${cut}px 切线`);
    chipRemove.addEventListener("click", () => removeManualCut(cut));
    chip.append(chipText, chipRemove);
    cutList.appendChild(chip);
  }

  const segments = manualCutState.cuts.length + 1;
  const maxHeight = getChunkHeightLimit();
  const maxHeightText = Number.isInteger(maxHeight) ? `，最大高度 ${maxHeight}px` : "";
  setPreviewStatus(
    `预览 ${manualCutState.outputWidth}x${manualCutState.outputHeight}，已标记 ${manualCutState.cuts.length} 条切线，导出 ${segments} 段${maxHeightText}。`
  );
}

function markManualPreviewStale() {
  if (!manualCutState.signature) return;
  manualCutState.signature = "";
  setPreviewStatus("图片或缩放参数已变化，请重新加载预览。");
}

function buildResultCard(fileName, width, height, layout, cardSlices) {
  const card = document.createElement("article");
  card.className = "result-card";

  const header = document.createElement("div");
  header.className = "result-header";

  const title = document.createElement("div");
  title.className = "result-title";
  title.textContent = fileName;

  const meta = document.createElement("div");
  meta.className = "meta";
  const sizeText = layout.resized
    ? `原图 ${width}x${height}，输出 ${layout.outputWidth}x${layout.outputHeight}（高度向下取整）`
    : `原图 ${width}x${height}`;
  meta.textContent = `${sizeText}，${formatSliceMode(layout)}，切出 ${layout.total} 张`;

  const downloadBtn = document.createElement("button");
  downloadBtn.type = "button";
  downloadBtn.className = "pill-btn shadow";
  downloadBtn.textContent = "下载该图全部切片";
  downloadBtn.addEventListener("click", () => downloadSlices(cardSlices, `${fileName}_slices.zip`, downloadBtn));

  header.append(title, meta, downloadBtn);
  card.appendChild(header);

  const thumbs = document.createElement("div");
  thumbs.className = "thumbs";
  for (const item of cardSlices) {
    const t = document.createElement("div");
    t.className = "thumb";
    const img = document.createElement("img");
    img.src = item.previewUrl;
    img.loading = "lazy";
    img.alt = item.name;
    const cap = document.createElement("div");
    cap.className = "cap";
    cap.textContent = item.name;
    const link = document.createElement("a");
    link.href = item.previewUrl;
    link.download = item.name;
    link.title = "下载这张切片";
    link.append(img, cap);
    t.appendChild(link);
    thumbs.appendChild(t);
  }

  card.appendChild(thumbs);
  resultsEl.appendChild(card);
  syncResultSummary();
}

function getSliceSegments(outputHeight, chunkHeight, manualCuts) {
  if (manualCuts) {
    const boundaries = [0, ...getSortedCuts(manualCuts, outputHeight), outputHeight];
    return boundaries.slice(0, -1).map((top, index) => ({
      top,
      bottom: boundaries[index + 1],
    }));
  }

  const rows = Math.ceil(outputHeight / chunkHeight);
  return Array.from({ length: rows }, (_, row) => {
    const top = row * chunkHeight;
    return {
      top,
      bottom: Math.min((row + 1) * chunkHeight, outputHeight),
    };
  });
}

function getManualMaxHeightError(cuts, outputHeight, maxHeight) {
  if (!Number.isInteger(maxHeight) || maxHeight <= 0) {
    return "切片最大高度必须是大于 0 的整数。";
  }

  const segments = getSliceSegments(outputHeight, maxHeight, cuts);
  const oversized = segments.find((segment) => segment.bottom - segment.top > maxHeight);
  if (!oversized) return "";

  const height = oversized.bottom - oversized.top;
  return `仍有手动裁切段超过最大高度：Y ${oversized.top}-${oversized.bottom}，高度 ${height}px；请补充裁切标记。`;
}

async function sliceOneFile(file, targetWidth, chunkWidth, chunkHeight, manualCuts = null) {
  const bitmap = await loadBitmap(file);
  const width = bitmap.width;
  const height = bitmap.height;
  const output = getOutputSize(width, height, targetWidth);
  const columns = Math.ceil(output.outputWidth / chunkWidth);
  const segments = getSliceSegments(output.outputHeight, chunkHeight, manualCuts);
  const { mime, ext } = getFileExt(file);
  const baseName = file.name.replace(/\.[^.]+$/, "");
  const outputBaseName = output.resized
    ? `${baseName}_w${output.outputWidth}`
    : baseName;
  const chunks = [];

  try {
    for (let row = 0; row < segments.length; row += 1) {
      const { top, bottom } = segments[row];
      const partHeight = bottom - top;

      for (let column = 0; column < columns; column += 1) {
        const left = column * chunkWidth;
        const right = Math.min((column + 1) * chunkWidth, output.outputWidth);
        const partWidth = right - left;

        const canvas = document.createElement("canvas");
        canvas.width = partWidth;
        canvas.height = partHeight;
        const ctx = canvas.getContext("2d", { alpha: mime !== "image/jpeg" });
        if (!ctx) throw new Error("图片尺寸过大，无法生成切片，请减小切片尺寸。");
        const sourceLeft = (left * width) / output.outputWidth;
        const sourceTop = (top * height) / output.outputHeight;
        const sourceWidth = (partWidth * width) / output.outputWidth;
        const sourceHeight = (partHeight * height) / output.outputHeight;
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(
          bitmap,
          sourceLeft,
          sourceTop,
          sourceWidth,
          sourceHeight,
          0,
          0,
          partWidth,
          partHeight
        );

        const blob = await toBlob(canvas, mime);
        const previewUrl = URL.createObjectURL(blob);
        objectUrls.push(previewUrl);

        let name = `${outputBaseName}_r${String(row + 1).padStart(
          2,
          "0"
        )}-c${String(column + 1).padStart(2, "0")}_x${String(left).padStart(
          5,
          "0"
        )}-${String(right).padStart(5, "0")}_y${String(top).padStart(
          5,
          "0"
        )}-${String(bottom).padStart(5, "0")}.${ext}`;
        const originalName = name;
        let duplicate = 2;
        while (allSlices.some(item => item.name === name)) {
          name = originalName.replace(/(\.[^.]+)$/, `_${duplicate++}$1`);
        }
        const item = { name, blob, previewUrl };
        chunks.push(item);
        allSlices.push(item);
      }
    }

  } finally {
    if (typeof bitmap.close === "function") bitmap.close();
  }
  return {
    width,
    height,
    ...output,
    columns,
    rows: segments.length,
    manual: Boolean(manualCuts),
    chunks,
  };
}

function updateModeView() {
  const manualMode = cutModeInput.value === "manual";
  root.classList.toggle("is-manual", manualMode);
  manualPanel.hidden = !manualMode;
  getElement("resultActions").hidden = !manualMode;
  loadPreviewBtn.hidden = !manualMode;
  root.querySelectorAll("[data-mode]").forEach(button => {
    const selected = button.dataset.mode === cutModeInput.value;
    button.classList.toggle("on", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  getElement("modeHint").textContent = manualMode ? "指定切线，精确控制每一段" : "按最大尺寸，自动分行分列";
}

async function loadManualPreview() {
  if (busy) return;
  const files = Array.from(fileInput.files || []);
  const targetWidth = getTargetWidth();

  if (cutModeInput.value !== "manual") {
    setStatus("请先将裁切方式切换为定点裁切。");
    return;
  }
  revealPanel(manualPanel, "manualTitle");
  if (!files.length) {
    setPreviewStatus("请先选择一张图片。");
    return;
  }
  if (files.length > 1) {
    setPreviewStatus("定点裁切模式一次只支持一张图片。");
    return;
  }
  if (Number.isNaN(targetWidth)) {
    setPreviewStatus("输出宽度必须为空，或填写大于 0 的整数。");
    return;
  }

  const file = files[0];
  const signature = getPreviewSignature(file, targetWidth);
  setBusy(true);
  setPreviewStatus("正在加载预览...");

  try {
    const size = await readImageSize(file);
    const output = getOutputSize(size.width, size.height, targetWidth);
    resetManualCutState();

    manualCutState.signature = signature;
    manualCutState.width = size.width;
    manualCutState.height = size.height;
    manualCutState.outputWidth = output.outputWidth;
    manualCutState.outputHeight = output.outputHeight;
    manualCutState.resized = output.resized;
    manualCutState.previewUrl = URL.createObjectURL(file);

    previewImage.src = manualCutState.previewUrl;
    previewFrame.style.width = `${output.outputWidth}px`;
    previewFrame.style.aspectRatio = `${output.outputWidth} / ${output.outputHeight}`;
    previewFrame.hidden = false;
    renderManualCuts();
  } catch (error) {
    resetManualCutState();
    setPreviewStatus(`预览加载失败：${error.message || "未知错误"}`);
  } finally {
    setBusy(false);
  }
}

function getManualCutsForExport(files, targetWidth) {
  if (cutModeInput.value !== "manual") return null;
  if (files.length !== 1) {
    throw new Error("定点裁切模式一次只支持一张图片。");
  }

  const signature = getPreviewSignature(files[0], targetWidth);
  if (!manualCutState.signature || manualCutState.signature !== signature) {
    throw new Error("请先加载当前图片的定点裁切预览。");
  }

  return manualCutState.cuts;
}

sliceBtn.addEventListener("click", async () => {
  if (busy) return;
  revealPanel(resultPanel, "resultTitle");
  const files = Array.from(fileInput.files || []);
  const targetWidth = getTargetWidth();
  const chunkWidth = Number(chunkWidthInput.value);
  const chunkHeight = Number(chunkHeightInput.value);
  let manualCuts = null;

  if (!files.length) {
    setStatus("请先选择至少一张图片。");
    return;
  }
  if (Number.isNaN(targetWidth)) {
    setStatus("输出宽度必须为空，或填写大于 0 的整数。");
    return;
  }
  if (!Number.isInteger(chunkWidth) || chunkWidth <= 0) {
    setStatus("切片最大宽度必须是大于 0 的整数。");
    return;
  }
  if (!Number.isInteger(chunkHeight) || chunkHeight <= 0) {
    setStatus("切片最大高度必须是大于 0 的整数。");
    return;
  }
  if (typeof JSZip === "undefined") {
    setStatus("打包组件加载失败，请刷新页面后重试。");
    return;
  }
  try {
    manualCuts = getManualCutsForExport(files, targetWidth);
  } catch (error) {
    setStatus(error.message);
    return;
  }
  if (manualCuts !== null) {
    const maxHeightError = getManualMaxHeightError(
      manualCuts,
      manualCutState.outputHeight,
      chunkHeight
    );
    if (maxHeightError) {
      setStatus(maxHeightError);
      return;
    }
  }

  resetView();
  setBusy(true);
  setStatus(`处理中：共 ${files.length} 张图片...`);

  try {
    let done = 0;
    for (const file of files) {
      const completedCount = allSlices.length;
      try {
        const result = await sliceOneFile(
          file,
          targetWidth,
          chunkWidth,
          chunkHeight,
          manualCuts
        );
        buildResultCard(
          file.name,
          result.width,
          result.height,
          {
            columns: result.columns,
            rows: result.rows,
            total: result.chunks.length,
            outputWidth: result.outputWidth,
            outputHeight: result.outputHeight,
            resized: result.resized,
            manual: result.manual,
          },
          result.chunks
        );
      } catch (error) {
        allSlices.splice(completedCount).forEach(item => {
          URL.revokeObjectURL(item.previewUrl);
          const index = objectUrls.indexOf(item.previewUrl);
          if (index >= 0) objectUrls.splice(index, 1);
        });
        throw new Error(`${file.name}：${error.message}`);
      }
      done += 1;
      setStatus(`处理中：${done}/${files.length} 张完成...`);
    }

    downloadZipBtn.disabled = allSlices.length === 0;
    const resizeText =
      targetWidth === null
        ? "保持原图宽度"
        : `先缩放到 ${targetWidth}px 宽，高度向下取整`;
    const modeText =
      manualCuts === null
        ? `按最大 ${chunkWidth}x${chunkHeight}px 自动切片`
        : `按 ${manualCuts.length} 条定点切线裁切，分段高度不超过 ${chunkHeight}px，每张最大宽度 ${chunkWidth}px`;
    setStatus(`完成：共切出 ${allSlices.length} 张切片（${resizeText}；${modeText}）。`);
  } catch (error) {
    downloadZipBtn.disabled = allSlices.length === 0;
    syncResultSummary();
    setStatus(`处理失败：${error.message || "未知错误"}${allSlices.length ? "；已完成的切片仍可下载。" : ""}`);
  } finally {
    setBusy(false);
  }
});

clearBtn.addEventListener("click", () => {
  fileInput.value = "";
  updateFileSummary();
  resetView();
  resetManualCutState();
  setStatus("已清空。请重新选择图片。");
});

cutModeInput.addEventListener("change", () => {
  updateModeView();
});

fileInput.addEventListener("change", () => {
  resetManualCutState();
  updateFileSummary();
  resetView();
  setStatus(fileInput.files.length ? "图片已更新，设置尺寸后点击“开始切图”。" : "已取消选择。请重新选择图片。");
});

targetWidthInput.addEventListener("input", () => {
  markManualPreviewStale();
});

chunkHeightInput.addEventListener("input", () => {
  if (manualCutState.outputHeight) {
    renderManualCuts();
  }
});

loadPreviewBtn.addEventListener("click", () => {
  loadManualPreview();
});

cutOverlay.addEventListener("pointermove", (event) => {
  if (event.pointerType === "touch") return;
  const y = getPointerCutY(event);
  if (y === null) return;
  showKnifeGuide(y);
});

cutOverlay.addEventListener("pointerleave", () => {
  hideKnifeGuide();
});

cutOverlay.addEventListener("click", (event) => {
  if (event.target.closest("button")) return;
  if (!manualCutState.outputHeight) {
    setPreviewStatus("请先加载预览。");
    return;
  }

  const y = getPointerCutY(event);
  if (y === null) return;
  if (addManualCut(getPointerCutTarget(y))) showKnifeGuide(y);
});

addCutYBtn.addEventListener("click", () => {
  const y = Number(cutYInput.value);
  if (!manualCutState.outputHeight) { setPreviewStatus("请先加载预览。"); return; }
  if (!cutYInput.value.trim() || !Number.isInteger(y) || y < 1 || y >= manualCutState.outputHeight) {
    setPreviewStatus(`Y 坐标必须是 1 到 ${manualCutState.outputHeight - 1} 之间的整数。`);
    return;
  }
  if (addManualCut(y)) {
    cutYInput.value = "";
  }
});

cutYInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  addCutYBtn.click();
});

clearCutsBtn.addEventListener("click", () => {
  manualCutState.cuts = [];
  renderManualCuts();
});

async function downloadSlices(items, filename, button) {
  if (!items.length || button.disabled) return;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "正在打包…";
  try {
    const zip = new window.JSZip();
    for (const item of items) zip.file(item.name, item.blob);
    const blob = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    setStatus(`下载失败：${error.message || "请重试"}`);
  } finally {
    button.textContent = label;
    button.disabled = button === downloadZipBtn && allSlices.length === 0;
  }
}
downloadZipBtn.addEventListener("click", () => downloadSlices([...allSlices], "image_slices.zip", downloadZipBtn));
root.querySelectorAll("[data-mode]").forEach(button => {
  button.addEventListener("click", () => {
    if (busy) return;
    cutModeInput.value = button.dataset.mode;
    updateModeView();
  });
});
const dropzone = getElement("dropzone");
dropzone.addEventListener("dragover", event => { event.preventDefault(); if (!busy) dropzone.classList.add("dragging"); });
dropzone.addEventListener("dragleave", event => { if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove("dragging"); });
dropzone.addEventListener("drop", event => {
  event.preventDefault(); dropzone.classList.remove("dragging");
  if (busy) return;
  const files = Array.from(event.dataTransfer.files);
  if (!files.length || files.some(file => !file.type.startsWith("image/"))) {
    setStatus("请拖入图片文件。"); return;
  }
  const transfer = new DataTransfer();
  files.forEach(file => transfer.items.add(file));
  fileInput.files = transfer.files;
  fileInput.dispatchEvent(new Event("change"));
});
updateModeView();
return root;
}
