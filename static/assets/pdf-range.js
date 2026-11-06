/* Air exposes Content-Length on HEAD, but not Accept-Ranges through CORS.
   Use PDF.js's public range transport so opening a PDF never fetches it all. */
export async function airPDFRange(lib, href, controller, onError) {
  const head = await fetch(href, {method:'HEAD', signal:AbortSignal.any([controller.signal, AbortSignal.timeout(30000)])});
  const length = Number(head.headers.get('Content-Length'));
  if (!head.ok || !Number.isSafeInteger(length) || length <= 0) throw new Error('无法读取文档大小');
  return new class extends lib.PDFDataRangeTransport {
    constructor() { super(length, null, true); }
    active = 0;
    pending = [];
    requestDataRange(begin, end) {
      this.pending.push(async () => {
        if (controller.signal.aborted) return;
        for (let attempt = 0; attempt < 2; attempt++) {
          try {
            const response = await fetch(href, {headers:{Range:`bytes=${begin}-${end - 1}`},
              signal:AbortSignal.any([controller.signal, AbortSignal.timeout(30000)])});
            if (response.status !== 206) { await response.body?.cancel(); throw new Error('文档分段读取失败'); }
            const chunk = new Uint8Array(await response.arrayBuffer());
            if (chunk.byteLength !== end - begin) throw new Error('文档分段不完整');
            if (!controller.signal.aborted) this.onDataRange(begin, chunk);
            return;
          } catch (error) {
            if (controller.signal.aborted) return;
            if (attempt === 1) onError(error);
          }
        }
      });
      this.pump();
    }
    pump() {
      while (this.active < 4 && this.pending.length && !controller.signal.aborted) {
        const request = this.pending.shift(); this.active++;
        request().finally(() => { this.active--; this.pump(); });
      }
    }
    abort() { controller.abort(); }
  }();
}
