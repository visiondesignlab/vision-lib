/* Export geometry is copied from the reviewed Capture V6 demo/Figma layers. */
export function createScreenshotExporter(data, catalogURL) {
  const sources = new Map(), images = new Map(), renders = new Map();
  const resolve = path => new URL(path, catalogURL).href;
  async function source(path) {
    const url = resolve(path);
    if (!sources.has(url)) sources.set(url, fetch(url).then(response => {
      if (!response.ok) throw new Error('素材载入失败，请重试。');
      return response.blob();
    }).catch(error => { sources.delete(url); throw error; }));
    return sources.get(url);
  }
  function image(path) {
    const url = resolve(path);
    if (!images.has(url)) images.set(url, new Promise((resolveImage, reject) => {
      const img = new Image();
      img.onload = () => resolveImage(img);
      img.onerror = () => { images.delete(url); reject(new Error('图片载入失败，请重试。')); };
      img.src = url;
    }));
    return images.get(url);
  }
  function dimensions(mode, scale) {
    return (mode === 'raw' ? data.mockup.screen : data.mockup.canvas[mode]).map(value => value * scale);
  }
  function filename(id, {locale, mode, scale}) {
    const style = {raw:'original', shadow:'mockup-shadow', clean:'mockup-no-shadow'}[mode];
    return `viaim_${id}_${locale}_${style}@${scale}x.png`;
  }
  async function render(id, {locale, mode, scale}) {
    const item = data.items.find(item => item.id === id), shot = item?.locales[locale];
    if (!shot || !['raw','shadow','clean'].includes(mode) || ![1,2,3].includes(scale)) throw new Error('请选择有效的截图与导出设置。');
    // Fetch the actual PNG unchanged; Canvas must never re-encode native @3x.
    if (mode === 'raw' && scale === 3) return source(shot.src);
    const key = [id,locale,mode,scale].join('|');
    if (renders.has(key)) return renders.get(key);
    const promise = (async () => {
      const original = await image(shot.src), [width,height] = dimensions(mode,scale);
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('浏览器无法创建图片，请使用新版浏览器。');
      ctx.scale(scale,scale); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
      const [sw,sh] = data.mockup.screen;
      if (mode === 'raw') ctx.drawImage(original,0,0,sw,sh);
      else {
        const [frame,shadow] = await Promise.all([image(data.mockup.frame),mode === 'shadow' ? image(data.mockup.shadow) : null]);
        const [x,y] = data.mockup.inset, [sx,sy,swidth,sheight] = data.mockup.shadowBounds;
        if (shadow) ctx.drawImage(shadow,x+sx,y+sy,swidth,sheight);
        ctx.save(); ctx.beginPath(); ctx.roundRect(x,y,sw,sh,data.mockup.screenRadius); ctx.clip();
        ctx.drawImage(original,x,y,sw,sh); ctx.restore();
        const [fx,fy,fw,fh] = data.mockup.frameBounds; ctx.drawImage(frame,x+fx,y+fy,fw,fh);
      }
      return new Promise((resolveBlob,reject) => canvas.toBlob(blob => blob ? resolveBlob(blob) : reject(new Error('PNG 导出失败，请重试。')),'image/png'));
    })();
    renders.set(key,promise);
    if (renders.size > 12) renders.delete(renders.keys().next().value);
    promise.catch(() => renders.delete(key));
    return promise;
  }
  return {resolve, dimensions, filename, render};
}
