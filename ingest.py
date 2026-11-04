#!/usr/bin/env python3
"""Daily ingest for Launch 案例库. Adds NEW candidates as status=pending (or published with --publish),
deduped against every existing case's source URL and against data/rejected.json.

Sources
  github   GitHub repository search (public API) for video-related agent-skill repos.
           Set GITHUB_TOKEN to raise the rate limit (optional).
  inbox    JSON files dropped into data/inbox/*.json by an outside agent (X post candidates).
           Each file: a list (or {"items": [...]}) of objects:
             {"type": "case" | "showcase",          # case = 视频案例(带复现方法)  showcase = 灵感库(纯展示)
              "url": "https://x.com/<user>/status/<id>", "author": "@user", "title": "...",
              "text": "post text", "date": "2026-11-03", "metrics": {"views":0,"likes":0,"reposts":0,"bookmarks":0},
              "media_urls": ["https://video.twimg.com/...mp4" | "https://pbs.twimg.com/...jpg"],
              "category": "营销产品", "tags": ["..."], "brand": "..."}
           Media is downloaded (direct URL, else yt-dlp on the post URL); a thumbnail is made with ffmpeg.
           Processed files move to data/inbox/processed/.
  lvg      launchvideos.gallery (灵感库 showcase source). Reads the public listing pages (home, /latest and
           the category pages listed in its sitemap) and parses the listing data the site server-renders
           into the HTML. Respects robots.txt (never touches /api/, /admin, /saved), 2s between requests.
           Uses the listing only for discovery, then downloads the X original and caches MP4, preview, thumbnail and author avatar.

Usage
  python3 ingest.py                      # all sources, new items -> pending
  python3 ingest.py --sources lvg,inbox  # subset
  python3 ingest.py --sources lvg --publish --limit 50   # first bulk import, published
  python3 ingest.py --dry-run            # show what would be added
Exit code 0 on success; prints a one-line JSON summary at the end (for the scheduler's log).
"""
import argparse, glob, html, json, os, re, shutil, sys, time, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone
import store, mediautil, xsource

UA = "LaunchCaseLib-ingest/1.0 (+internal team gallery; polite crawler)"
LVG = "https://launchvideos.gallery"
LVG_CAT = {"agents": "Agent", "ai": "AI", "brand-films": "品牌片", "consumer": "消费", "crypto": "加密",
           "deep-tech": "硬科技", "design": "设计", "developer-tools": "开发者工具", "fintech": "金融科技",
           "funding": "融资发布", "hardware": "硬件", "health": "健康", "motion": "动效", "other": "其他",
           "productivity": "效率", "studio-work": "工作室作品", "video-image-gen": "视频图像生成", "voice-audio": "语音音频"}
GH_QUERIES = ["remotion skill", "hyperframes", "motion graphics skill claude", "ffmpeg skill agent",
              "video skill claude code", "launch video agent", "video editing agent skill", "motion design skill"]


def log(*a):
    print("[ingest]", *a, file=sys.stderr)


def get(url, timeout=30, headers=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def base_record(**kw):
    rec = dict(type="video", category="", title="", subtitle="", media={}, source={}, prompt="", how_to=[],
               skills=[], tools=[], assets=[], tags=[], featured=False, trust="社区", status="pending",
               version="1.0.0", added_at=store.now_iso(), updated_at=store.now_iso(), ingested_by="ingest.py")
    rec.update(kw)
    return rec


# ------------------------------------------------------------------ GitHub
def src_github(known, limit):
    out, tok = [], os.environ.get("GITHUB_TOKEN")
    hdr = {"Accept": "application/vnd.github+json"}
    if tok:
        hdr["Authorization"] = "Bearer " + tok
    since = (datetime.now(timezone.utc).date().replace(day=1)).isoformat()
    for q in GH_QUERIES:
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": f"{q} pushed:>={since}", "sort": "stars", "order": "desc", "per_page": 15})
        try:
            items = json.loads(get(url, headers=hdr)).get("items", [])
        except Exception as e:
            log("github search failed:", q, e)
            items = []
        for it in items:
            u = it["html_url"]
            if store.norm_url(u) in known or it.get("fork") or it.get("archived"):
                continue
            if (it.get("stargazers_count") or 0) < 20:
                continue
            known.add(store.norm_url(u))
            repo = it["full_name"]
            cid = "repo-" + store.slug(repo)
            thumb = ""
            try:
                d = os.path.join(store.MEDIA, cid); os.makedirs(d, exist_ok=True)
                mediautil.http_download(f"https://opengraph.githubassets.com/1/{repo}", os.path.join(d, "thumb.png"))
                thumb = f"/media/{cid}/thumb.png"
            except Exception:
                thumb = mediautil.placeholder_thumb(cid, repo.split("/")[1], repo)
            out.append(base_record(
                id=cid, type="skill_repo", category="待分类", title=repo.split("/")[1],
                subtitle=(it.get("description") or "")[:140],
                media={"kind": "image", "thumbnail": thumb, "video": "", "preview": "", "images": []},
                source={"platform": "GitHub", "author": it["owner"]["login"], "author_url": it["owner"]["html_url"],
                        "url": u, "repo": repo, "date": (it.get("created_at") or "")[:10],
                        "metrics": {"stars": it.get("stargazers_count"), "forks": it.get("forks_count")},
                        "metrics_fetched_at": datetime.now(store.CST).strftime("%Y-%m-%d"),
                        "note": f"GitHub 搜索「{q}」命中"},
                prompt=f"把 {repo} 安装为这个 coding agent 的 skill：克隆 {u} ，阅读 README，把整个文件夹放进 skills 目录。然后按 README 的示例做一支 30 秒产品 launch 视频，先给我镜头表确认。",
                how_to=["审核时先打开仓库确认与视频制作相关，再补充用途、分类和步骤。"],
                skills=[{"name": repo.split("/")[1], "repo": repo, "url": u}],
                tags=["GitHub 搜索", q] + (it.get("topics") or [])[:5]))
            if len(out) >= limit:
                return out
        time.sleep(7 if not tok else 1)  # unauthenticated search: 10 req/min
    return out


# ------------------------------------------------------------------ inbox (outside agent drops X candidates)
def _media_from(item, cid):
    vids = [u for u in item.get("media_urls") or [] if re.search(r"\.(mp4|mov|webm)(\?|$)", u)]
    imgs = [u for u in item.get("media_urls") or [] if re.search(r"\.(jpe?g|png|webp)(\?|$)|format=(jpg|png)", u)]
    tmp = os.path.join("/tmp", "caselib-" + cid)
    os.makedirs(tmp, exist_ok=True)
    src = None
    for u in vids:
        try:
            src = mediautil.http_download(u, os.path.join(tmp, "v.mp4"), timeout=180); break
        except Exception as e:
            log("media download failed", u, e)
    if not src and item.get("url") and not imgs:
        src = mediautil.ytdlp_download(item["url"], os.path.join(tmp, "v"))
    if src:
        m = mediautil.process_video(src, cid)
        shutil.rmtree(tmp, ignore_errors=True)
        return m
    if imgs:
        paths = []
        for i, u in enumerate(imgs[:8]):
            try:
                paths.append(mediautil.http_download(u, os.path.join(tmp, f"i{i}.jpg")))
            except Exception as e:
                log("image download failed", u, e)
        if paths:
            m = mediautil.process_images(paths, cid)
            shutil.rmtree(tmp, ignore_errors=True)
            return m
    return {"kind": "none", "video": "", "preview": "", "images": [],
            "thumbnail": mediautil.placeholder_thumb(cid, item.get("title") or item.get("author") or "X 候选", "暂无可下载媒体，请看原帖")}


def src_inbox(known, limit):
    out = []
    files = sorted(glob.glob(os.path.join(store.DATA, "inbox", "*.json")))
    for f in files:
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            log("bad inbox file", f, e); continue
        items = j.get("items", []) if isinstance(j, dict) else j
        for it in items:
            u = it.get("url") or ""
            n = store.norm_url(u)
            if not n or n in known:
                continue
            known.add(n)
            kind = it.get("type") or "case"
            pid = n.rsplit("/", 1)[-1]
            cid = ("show-" if kind == "showcase" else "x-") + store.slug(pid)
            author = it.get("author") or ""
            if author and not author.startswith("@"):
                author = "@" + author
            title = it.get("title") or (it.get("text") or "").split("\n")[0][:60] or author
            media = _media_from(it, cid)
            src = {"platform": it.get("platform") or "X", "author": author,
                   "author_url": ("https://x.com/" + author[1:]) if author else "", "url": u,
                   "metrics": it.get("metrics") or {}, "metrics_fetched_at": it.get("metrics_fetched_at") or it.get("fetched_at") or "",
                   "date": it.get("date") or "", "post_text": it.get("text") or "", "via": "inbox:" + os.path.basename(f)}
            if kind == "showcase":
                rec = base_record(id=cid, type="showcase", category=it.get("category") or "其他", title=title,
                                  brand=it.get("brand") or author.lstrip("@"), subtitle=it.get("brand") or author,
                                  media=media, source=src, tags=it.get("tags") or [])
            else:
                rec = base_record(id=cid, type="video", category=it.get("category") or "营销产品", title=title,
                                  subtitle=(it.get("text") or "")[:100], media=media, source=src, tags=it.get("tags") or [],
                                  prompt="（待审核时补充复现 Prompt）", how_to=["（待审核时补充复现步骤）"])
            if xsource.post_id(u):
                rec, errors = xsource.enrich(rec, with_video=False)
                if errors:
                    log("X author metadata", cid, "; ".join(errors))
            out.append(rec)
            if len(out) >= limit:
                break
        dst = os.path.join(store.DATA, "inbox", "processed", time.strftime("%Y%m%d-%H%M%S-") + os.path.basename(f))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(f, dst)
    return out


# ------------------------------------------------------------------ launchvideos.gallery
def _lvg_robots():
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(get(LVG + "/robots.txt").splitlines())
    except Exception as e:
        log("robots.txt unreadable, only fetching / and /latest", e)
        rp.parse(["User-agent: *", "Allow: /$", "Allow: /latest", "Disallow: /"])
    return rp


def _lvg_records(page_html):
    recs = []
    for m in re.finditer(r'<script type="application/json" data-sveltekit-fetched data-url="([^"]+)"[^>]*>(.*?)</script>', page_html, re.S):
        if "launchvideos_posts" not in html.unescape(m.group(1)):
            continue
        try:
            j = json.loads(m.group(2))
            body = json.loads(j["body"])
        except Exception:
            continue
        if isinstance(body, list):
            recs += [r for r in body if isinstance(r, dict) and r.get("id") and r.get("source_url")]
    return recs


def lvg_fetch_listing(max_pages=None):
    rp = _lvg_robots()
    pages = [LVG + "/", LVG + "/latest"]
    try:
        sm = get(LVG + "/sitemap.xml")
        pages += sorted(set(re.findall(r"<loc>(https://launchvideos\.gallery/category/[a-z0-9-]+)</loc>", sm)))
    except Exception as e:
        log("lvg sitemap failed", e)
    if max_pages:
        pages = pages[:max_pages]
    seen = {}
    for i, p in enumerate(pages):
        if not rp.can_fetch(UA, p):
            log("robots.txt disallows", p); continue
        if i:
            time.sleep(2.0)
        try:
            for r in _lvg_records(get(p)):
                seen.setdefault(r["id"], r)
        except Exception as e:
            log("lvg page failed", p, e)
    recs = list(seen.values())
    recs.sort(key=lambda r: r.get("posted_at") or r.get("published_at") or "", reverse=True)
    return recs, len(pages)


def lvg_to_case(r, status, dry=False):
    cid = "lvg-" + r["id"][:8]
    thumb = (r.get("thumbnail_url") or "") if dry else ""
    cats = [LVG_CAT.get(c, c) for c in (r.get("categories") or [])]
    brand = (r.get("brand") or {})
    st = r.get("stats") or {}
    posted = r.get("posted_at") or ""
    date = ""
    if posted:
        date = datetime.fromisoformat(posted.replace("Z", "+00:00")).astimezone(store.CST).strftime("%Y-%m-%d %H:%M") + "（北京时间）"
    src_url = r.get("source_url") or ""
    platform = "X" if re.search(r"(x|twitter)\.com/", src_url) else ("YouTube" if "youtu" in src_url else "网页")
    fetched = (r.get("stats_updated_at") or "")[:10]
    case = base_record(
        id=cid, type="showcase", status=status, category=cats[0] if cats else "其他",
        title=r.get("title") or brand.get("name") or "", brand=brand.get("name") or r.get("brand_username") or "",
        subtitle=r.get("tagline") or (r.get("description") or "")[:80], description=r.get("description") or "",
        media={"kind": "video", "embed": "remote", "remote_video": r.get("original_media_url") or "",
               "video": "", "preview": "", "images": [], "thumbnail": thumb},
        source={"platform": platform, "author": "@" + (r.get("brand_username") or brand.get("username") or ""),
                "author_url": "https://x.com/" + (r.get("brand_username") or "") if platform == "X" else (brand.get("url") or ""),
                "url": src_url, "video_source_url": src_url, "brand_site": brand.get("url") or "",
                "metrics": {"views": st.get("viewCount"), "likes": st.get("favoriteCount"), "reposts": st.get("retweetCount"),
                            "bookmarks": st.get("bookmarkCount"), "replies": st.get("replieCount")},
                "metrics_fetched_at": fetched + "（launchvideos.gallery 记录）" if fetched else "",
                "date": date, "via": "launchvideos.gallery", "via_url": f"{LVG}/videos/{r['id']}"},
        tags=cats + ["launchvideos.gallery"], lvg_id=r["id"])
    if not dry:
        case, errors = xsource.enrich(case)
        if errors:
            log("X source enrichment", cid, "; ".join(errors))
        if not case["media"].get("thumbnail"):
            case["media"]["thumbnail"] = mediautil.placeholder_thumb(cid, case["title"], "请在 X 原帖查看视频")
    return case


def src_lvg(known, limit, status, dry=False):
    recs, npages = lvg_fetch_listing()
    log(f"lvg: {len(recs)} entries from {npages} listing pages")
    out = []
    for r in recs:
        n = store.norm_url(r.get("source_url"))
        vn = store.norm_url(f"{LVG}/videos/{r['id']}")
        if not n or n in known or vn in known:
            continue
        known.add(n); known.add(vn)
        out.append(lvg_to_case(r, status, dry))
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="github,inbox,lvg")
    ap.add_argument("--limit", type=int, default=30, help="max new items per source")
    ap.add_argument("--publish", action="store_true", help="add as published instead of pending (bulk seed)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    status = "published" if a.publish else "pending"
    cases = store.load_cases()
    known = store.known_urls(cases)
    for c in cases:
        discovery_url = c.get("discovery", {}).get("url") or c.get("source", {}).get("via_url")
        if discovery_url:
            known.add(store.norm_url(discovery_url))
    new, summary = [], {}
    for s in a.sources.split(","):
        s = s.strip()
        fn = {"github": lambda: src_github(known, a.limit), "inbox": lambda: src_inbox(known, a.limit),
              "lvg": lambda: src_lvg(known, a.limit, status, a.dry_run)}.get(s)
        if not fn:
            log("unknown source", s); continue
        if a.dry_run and s == "inbox":
            summary[s] = "skipped in dry-run"; continue
        got = fn()
        for g in got:
            if s != "lvg":
                g["status"] = status
        summary[s] = len(got)
        new += got
    if a.dry_run:
        for n in new:
            print(n["type"], n["id"], n["title"], n["source"].get("url"))
    else:
        with store.locked():
            cur = store.load_cases()
            ids = {c["id"] for c in cur}
            add = [n for n in new if n["id"] not in ids]
            store.save_cases(cur + add)
    print(json.dumps({"ok": True, "added": len(new), "by_source": summary, "status": status,
                      "at": store.now_iso()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
