// Public clients can deposit a link. Only the local CMS can read the inbox.
import {DurableObject} from "cloudflare:workers";

function reply(body, status = 200, headers = {}) {
  return Response.json(body, {status, headers: {"Cache-Control":"no-store", ...headers}});
}

export class Inbox extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec("CREATE TABLE IF NOT EXISTS submissions (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, url TEXT, title TEXT, note TEXT, created TEXT)");
    this.sql.exec("CREATE TABLE IF NOT EXISTS limits (bucket TEXT PRIMARY KEY, slot INTEGER, count INTEGER)");
  }
  deposit(item, bucket) {
    if (this.sql.exec("SELECT 1 FROM submissions WHERE id=?", item.id).toArray().length) return true;
    const slot = Math.floor(Date.now() / 600000);
    this.sql.exec("DELETE FROM limits WHERE slot < ?", slot);
    const previous = this.sql.exec("SELECT count FROM limits WHERE bucket=?", bucket).toArray()[0];
    if (previous?.count >= 15) return false;
    this.sql.exec("INSERT INTO limits VALUES(?,?,1) ON CONFLICT(bucket) DO UPDATE SET count=count+1", bucket, slot);
    this.sql.exec("INSERT INTO submissions(id,url,title,note,created) VALUES(?,?,?,?,?)",
      item.id, item.url, item.title, item.note, new Date().toISOString());
    return true;
  }
  list(after) {
    return this.sql.exec("SELECT * FROM submissions WHERE seq>? ORDER BY seq LIMIT 100", after).toArray();
  }
}

async function readBody(request) {
  const reader = request.body?.getReader();
  if (!reader) throw Error();
  const decoder = new TextDecoder();
  let size = 0, text = "";
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 16384) { await reader.cancel(); throw Error(); }
    text += decoder.decode(value, {stream:true});
  }
  return JSON.parse(text + decoder.decode());
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const inbox = env.INBOX.get(env.INBOX.idFromName("submissions"));
    if (url.pathname === "/sync" && request.method === "GET") {
      if (!env.READ_TOKEN || request.headers.get("Authorization") !== "Bearer " + env.READ_TOKEN)
        return reply({error:"需要管理员凭证"}, 401);
      const after = Number(url.searchParams.get("after") || 0);
      if (!Number.isSafeInteger(after) || after < 0) return reply({error:"无效的同步位置"}, 400);
      return reply({items:await inbox.list(after)});
    }
    if (url.pathname !== "/submissions") return reply({error:"入口不存在"}, 404);
    if (!env.SITE_ORIGIN || request.headers.get("Origin") !== env.SITE_ORIGIN) return reply({error:"来源无效"}, 403);
    const cors = {"Access-Control-Allow-Origin":env.SITE_ORIGIN, "Vary":"Origin",
      "Access-Control-Allow-Methods":"POST, OPTIONS", "Access-Control-Allow-Headers":"Content-Type"};
    if (request.method === "OPTIONS") return new Response(null, {status:204, headers:cors});
    if (request.method !== "POST") return reply({error:"仅支持投稿"}, 405, cors);
    if (request.headers.get("Content-Type")?.split(";")[0] !== "application/json") return reply({error:"请求格式有误"}, 415, cors);
    let item;
    try {
      const body = await readBody(request);
      const source = new URL(body.url);
      if (typeof body.url !== "string" || body.url.length > 2048 || /\s/.test(body.url) ||
          !["https:", "http:"].includes(source.protocol) || source.username || source.password ||
          !/^([a-z0-9.-]+)\.[a-z]{2,63}$/i.test(source.hostname) ||
          /\.(local|localhost|internal|test|invalid)$/i.test(source.hostname) ||
          (source.port && !['80','443'].includes(source.port)) || source.href.length>2048 ||
          typeof body.id !== 'string' || !/^[a-f0-9]{32}$/.test(body.id)) throw Error();
      if (typeof body.title !== "string" || typeof body.note !== "string" || body.title.length > 160 || body.note.length > 1600) throw Error();
      item = {id:body.id, url:source.href, title:body.title.trim(), note:body.note.trim()};
    } catch { return reply({error:"请提供完整的公开作品链接，并检查文字长度"}, 400, cors); }
    const ip = request.headers.get("CF-Connecting-IP") || "local";
    const hash = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(ip + ":" + Math.floor(Date.now()/600000)));
    const ok = await inbox.deposit(item, Array.from(new Uint8Array(hash)).join("."));
    return ok ? reply({receipt:item.id},201,cors) : reply({error:"提交过于频繁，请稍后再试"},429,cors);
  }
};
