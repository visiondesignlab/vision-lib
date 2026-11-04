"""Build data/cases.json from seed sources. Run once: python3 seed.py  (re-running rebuilds seed items,
keeps anything else that's already in cases.json, e.g. items added by ingest or edited in /review)."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import store, mediautil
from seed_data import *

LIVE = json.load(open(os.path.join(store.DATA, "_xposts_live.json"), encoding="utf-8"))
FETCHED = "2026-11-04"
BENCH_DIR = os.environ.get("BENCH_DIR", "/tmp/bench")


def cst(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(store.CST).strftime("%Y-%m-%d %H:%M")


def xmetrics(pid):
    m = LIVE[pid]["m"]
    return {"views": m["impression_count"], "likes": m["like_count"], "reposts": m["repost_count"],
            "bookmarks": m["bookmark_count"], "replies": m["reply_count"]}


def base(**kw):
    rec = dict(type="video", category="", title="", subtitle="", media={}, source={}, prompt="", how_to=[],
               skills=[], tools=[], assets=[], tags=[], featured=False, trust="社区", status="published",
               version="1.0.0", added_at=store.now_iso(), updated_at=store.now_iso(), notes="", seed=True)
    rec.update(kw)
    return rec


def build_ambi(a):
    pid = a["pid"]
    cid = "ambi-" + pid
    media = mediautil.process_video(f"/workspace/ambi/{pid}.mp4", cid)
    live = LIVE[pid]
    return base(id=cid, category=a["category"], title=a["title"], subtitle=a["subtitle"], media=media,
                source={"platform": "X", "author": "@hello_ambi", "author_url": "https://x.com/hello_ambi",
                        "url": f"https://x.com/hello_ambi/status/{pid}", "metrics": xmetrics(pid),
                        "metrics_fetched_at": FETCHED, "date": cst(live["created_at"]) + "（北京时间）",
                        "post_text": live["text"]},
                prompt=a["prompt"], how_to=a["how_to"], skills=a["skills"], tools=a["tools"],
                tags=a["tags"], analysis=a["kind_note"],
                assets=[{"name": "原片 MP4（站内转码）", "url": media["video"]},
                        {"name": "封面帧", "url": media["thumbnail"]}])


def build_bench(row):
    pid, handle, product, tlabel, spec, learn, cat = row
    cid = "bench-" + pid
    src = os.path.join(BENCH_DIR, pid + ".mp4")
    if os.path.exists(src):
        media = mediautil.process_video(src, cid)
    else:
        media = {"kind": "none", "video": "", "preview": "", "images": [],
                 "thumbnail": mediautil.placeholder_thumb(cid, product, tlabel + " · 无可下载视频，请看原帖")}
    route, sk, steps = route_for(tlabel)
    live = LIVE[pid]
    note = ""
    if pid == "2090865782246769016":
        note = "原帖正文只有一个链接；手册记录的「48 小时 11.7 万播放」是作者对影片的自述，与本帖浏览量不同。"
    return base(id=cid, category=cat, title=product, subtitle=f"{tlabel} · {spec}", media=media,
                source={"platform": "X", "author": "@" + live["user"], "author_url": "https://x.com/" + live["user"],
                        "url": f"https://x.com/{handle}/status/{pid}", "metrics": xmetrics(pid),
                        "metrics_fetched_at": FETCHED, "date": cst(live["created_at"]) + "（北京时间）",
                        "post_text": live["text"], "note": note},
                prompt=bench_prompt(product, tlabel, spec, learn), how_to=steps, skills=sk,
                tags=["标杆案例", tlabel], analysis="可学的点：" + learn + "（出自《X 产品 Launch Video 制作手册》§3 标杆案例库）",
                assets=([{"name": "原片 MP4（站内转码）", "url": media["video"]}] if media.get("video") else []))


def og_thumb(repo, cid):
    d = os.path.join(store.MEDIA, cid)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "thumb.png")
    if not os.path.exists(p):
        try:
            mediautil.http_download(f"https://opengraph.githubassets.com/1/{repo}", p, timeout=30)
        except Exception:
            return mediautil.placeholder_thumb(cid, repo.split("/")[1], repo)
    return f"/media/{cid}/thumb.png"


def skill_prompt(repo, use, install=None):
    inst = f"`{install}`" if install else f"克隆 https://github.com/{repo} ，阅读 README，把整个文件夹放进这个 agent 的 skills 目录（技能名和文件夹名保持一致）"
    return (f"把 {repo} 安装为这个 coding agent 的 skill：{inst}。\n\n"
            f"它的用途：{use}。\n\n"
            "装好后，用它为 {产品} 的 {功能} 做一支 30 秒 launch 视频：先读 README 里的用法和示例，"
            "给我一份带时长的镜头表（每个镜头：画面、两行标题 + 一句说明、声音），我确认后一次只做一个场景，"
            "最后导出 1920×1080、30fps 的 MP4，并另出一版 1080×1350 竖版。")


def build_skill(row):
    rank, repo, use, cat, post, author, views, likes, stars, date, group, note = row
    post = POSTS.get(post, post)
    cid = "repo-" + store.slug(repo)
    feat = repo in FEATURED
    why, install = FEATURED.get(repo, (None, None))
    how = ["打开 GitHub 仓库，先读 README 的安装方式和示例。",
           (f"安装：`{install}`" if install else "安装：在 agent 里粘贴上面的 Prompt，让它克隆并放进 skills 目录。"),
           "在一个空项目里先跑通官方示例，确认渲染环境（Node / ffmpeg / Chrome）都正常。",
           "再按 Prompt 让 agent 出镜头表 → 逐场景制作 → 导出。", BRAND_REF]
    return base(id=cid, type="skill_repo", category=cat, title=repo.split("/")[1], subtitle=use,
                media={"kind": "image", "images": [], "video": "", "preview": "", "thumbnail": og_thumb(repo, cid)},
                source={"platform": "GitHub", "author": repo.split("/")[0], "author_url": "https://github.com/" + repo.split("/")[0],
                        "url": "https://github.com/" + repo, "repo": repo,
                        "metrics": {"stars": stars, "post_views": views, "post_likes": likes},
                        "metrics_fetched_at": FETCHED, "date": date, "x_post": post, "x_author": "@" + author,
                        "note": note or "", "rank": rank, "group": group},
                prompt=skill_prompt(repo, use, install), how_to=how,
                skills=[{"name": repo.split("/")[1], "repo": repo, "url": "https://github.com/" + repo}],
                tags=[cat, group, "Top 50 #%d" % rank] + (["推荐"] if feat else []), featured=feat,
                analysis=(("推荐理由：" + why) if why else "") ,
                rank=rank)


def build_candidate(c):
    repo, stars, use, cat, note = c
    cid = "repo-" + store.slug(repo)
    return base(id=cid, type="skill_repo", category=cat, title=repo.split("/")[1], subtitle=use, status="pending",
                media={"kind": "image", "images": [], "video": "", "preview": "", "thumbnail": og_thumb(repo, cid)},
                source={"platform": "GitHub", "author": repo.split("/")[0], "author_url": "https://github.com/" + repo.split("/")[0],
                        "url": "https://github.com/" + repo, "repo": repo, "metrics": {"stars": stars},
                        "metrics_fetched_at": FETCHED, "note": "手册「候补（排在 50 名之后）」：" + note},
                prompt=skill_prompt(repo, use), how_to=["审核时先打开仓库确认仍可用，再补充用途和步骤。"],
                skills=[{"name": repo.split("/")[1], "repo": repo, "url": "https://github.com/" + repo}],
                tags=[cat, "候补"], seed=True)


def build_brand():
    cid = "brand-launch-video-spec"
    d = os.path.join(store.MEDIA, cid)
    thumb = mediautil.placeholder_thumb(cid, "Launch 视频通用规范", "品牌 Skill · v1.0.0 · 团队维护")
    body = open(os.path.join(store.ROOT, "brand_skills/launch-video-spec/SKILL.md"), encoding="utf-8").read()
    return base(id=cid, type="brand_skill", category="规范", title="Launch 视频通用规范",
                subtitle="脚本结构 · 画面字幕规则 · 导出规格 · 发布前 10 项自检", trust="官方", featured=True,
                media={"kind": "image", "images": [], "video": "", "preview": "", "thumbnail": thumb},
                source={"platform": "团队", "author": "Jiaqi Tang 团队", "url": PAGE,
                        "date": "2026-11-04", "note": "内容整理自 Page《X 产品 Launch Video 制作手册》"},
                prompt=("先读这份团队规范，再开始做视频：/brand_skills/launch-video-spec/SKILL.md 。\n"
                        "把它当作约束：镜头表要符合「脚本结构」，交付前逐条过「发布前 10 项自检」，"
                        "导出按「导出规格」。如果和别的 skill 冲突，以这份规范为准。\n\n" + body),
                how_to=["下载 SKILL.md，放到 agent 的 skills 目录（如 `.cursor/skills/launch-video-spec/SKILL.md`、`~/.claude/skills/launch-video-spec/SKILL.md` 或 `~/.codex/skills/launch-video-spec/SKILL.md`）。",
                        "做视频时在 Prompt 里点名使用 launch-video-spec。",
                        "规范更新时：改 brand_skills/launch-video-spec/SKILL.md，升 version，在 changelog 里写一行。"],
                assets=[{"name": "SKILL.md", "url": "/brand_skills/launch-video-spec/SKILL.md"}],
                tags=["品牌规范", "官方", "必读"], version="1.0.0",
                changelog=[{"version": "1.0.0", "date": "2026-11-04", "note": "首版：从制作手册整理脚本模板、字幕规则、导出规格、自检清单"}])


SHOW_IND = {'2109292120301519094': '消费', '2109660371296424352': '消费', '2109720765667172355': '消费', '2111109914303299925': '消费', '2112197075945308175': '消费', '2114733804535377947': '硬件', '2046736181002645520': '消费', '2036825558084878467': '效率', '1957489735527502301': '语音音频', '2107503346504634463': 'Agent', '2112335838801731970': '语音音频', '2080353769565348142': '效率', '1942213709088149719': '消费', '2105327223431737780': '视频图像生成', '1971211680664388053': '消费', '1947636878158565795': '消费', '2092175528396493189': '健康', '2029604182286856663': '开发者工具', '1942969263305671143': 'AI', '2115803472037572751': '效率'}
SHOW_CAT = {  # 灵感库 sub-category per post
 "2109292120301519094": ("预告", "Ambi"), "2109660371296424352": ("产品主片", "Ambi"), "2109720765667172355": ("真人广告", "Ambi"),
 "2111109914303299925": ("真人广告", "Ambi"), "2112197075945308175": ("真人广告", "Ambi"), "2114733804535377947": ("预告", "Ambi"),
 "2046736181002645520": ("产品主片", "X"), "2036825558084878467": ("产品主片", "Linear"), "1957489735527502301": ("产品主片", "ElevenLabs"),
 "2107503346504634463": ("产品主片", "ElevenLabs"), "2112335838801731970": ("功能短片", "Wispr Flow"), "2080353769565348142": ("功能短片", "Granola"),
 "1942213709088149719": ("功能短片", "Dia"), "2105327223431737780": ("产品主片", "Ideogram"), "1971211680664388053": ("AI 生成", "Memelord"),
 "1947636878158565795": ("AI 生成", "Whop"), "2092175528396493189": ("产品主片", "Marmar"), "2029604182286856663": ("产品主片", "Cursor"),
 "1942969263305671143": ("产品主片", "Perplexity"), "2115803472037572751": ("产品主片", "Raycast"),
}


def build_showcase(src_case):
    """Pure-showcase copy (灵感库): reuses the media of an existing case, simple metadata only."""
    pid = src_case["source"]["url"].rsplit("/", 1)[1]
    cat, brand = SHOW_CAT[pid]
    title = src_case["title"].replace("Ambi 上线预告：玻璃焦散文字", "Ambi 上线预告").replace("Ambi 主片：", "Ambi · ")
    title = title.replace("Ambi Moment", "Ambi Moment").replace("Ambi 硬件预告：", "Ambi 硬件预告 · ")
    sp = src_case["media"].get("specs") or {}
    return base(id="show-" + pid, type="showcase", category=SHOW_IND[pid], title=title, brand=brand,
                subtitle=" · ".join(x for x in [brand, sp.get("resolution", ""), (str(sp.get("duration_s")) + "s") if sp.get("duration_s") else ""] if x),
                media=src_case["media"], source={k: v for k, v in src_case["source"].items() if k != "note"},
                tags=[SHOW_IND[pid], cat, brand], format=cat, related=src_case["id"])


def main():
    with ThreadPoolExecutor(4) as ex:
        ambi = list(ex.map(build_ambi, AMBI))
        bench = list(ex.map(build_bench, BENCH))
    with ThreadPoolExecutor(8) as ex:
        skills = list(ex.map(build_skill, SKILLS))
        cands = list(ex.map(build_candidate, CANDIDATES))
    shows = [build_showcase(c) for c in ambi + bench if c["media"].get("kind") == "video"]
    seeded = ambi + bench + shows + skills + cands + [build_brand()]
    with store.locked():
        old = store.load_cases()
        ids = {r["id"] for r in seeded}
        keep = [c for c in old if c["id"] not in ids and not c.get("seed")]
        store.save_cases(seeded + keep)
    print(f"seeded {len(seeded)} (ambi {len(ambi)}, bench {len(bench)}, skills {len(skills)}, showcase {len(shows)}, pending {len(cands)}, brand 1); kept {len(keep)}")


if __name__ == "__main__":
    main()
