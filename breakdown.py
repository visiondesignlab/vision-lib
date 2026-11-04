"""一键拉片分析 (shot breakdown).

Structural analysis (always): ffmpeg scene detection -> shots, keyframe per shot, per-shot motion /
camera-move estimate (phase correlation), brightness & palette, pacing, audio (loudness, silence,
rough BPM, cut-on-beat ratio), optional OCR of on-screen text (if `tesseract` is installed), a
heuristic structure (hook / reveal / features / CTA) and a "可借鉴的手法" summary.

Vision (optional): if CASELIB_LLM_API_KEY is set, keyframes are sent to an OpenAI-compatible
chat-completions endpoint (CASELIB_LLM_BASE_URL, default https://api.openai.com/v1;
CASELIB_LLM_MODEL, default gpt-4o-mini) to describe 景别/运镜/画面/文字 per shot and the structure.

CLI:  python3 breakdown.py <case_id> [--force]
Cache: media/<media dir>/breakdown/breakdown.json
"""
import base64, json, os, re, shutil, subprocess, sys, time, urllib.request
import numpy as np
from PIL import Image
import store

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
TESS = shutil.which("tesseract")
VERSION = 1


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def video_path(case):
    v = (case.get("media") or {}).get("video") or ""
    if v.startswith("/media/"):
        p = os.path.join(store.ROOT, v.lstrip("/"))
        if os.path.exists(p):
            return p
    p = os.path.join(store.MEDIA, case["id"], "src.mp4")
    return p if os.path.exists(p) else None


def ensure_video(case):
    """Showcase items that only link/embed the original video get it downloaded here, once,
    purely for analysis (never re-served as the player source)."""
    vp = video_path(case)
    if vp:
        return vp
    import mediautil
    m = case.get("media") or {}
    dst = os.path.join(store.MEDIA, case["id"], "src.mp4")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if m.get("remote_video"):
        try:
            mediautil.http_download(m["remote_video"], dst, timeout=180)
            return dst
        except Exception:
            pass
    url = (case.get("source") or {}).get("video_source_url") or (case.get("source") or {}).get("url")
    if url:
        got = mediautil.ytdlp_download(url, dst[:-4])
        if got and got != dst:
            os.replace(got, dst)
        if os.path.exists(dst):
            return dst
    return None


def out_dir(case):
    return os.path.join(os.path.dirname(video_path(case)), "breakdown")


def cache_path(case):
    return os.path.join(out_dir(case), "breakdown.json")


def load_cached(case):
    vp = video_path(case)
    if not vp:
        return None
    p = cache_path(case)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


# ------------------------------------------------------------------ video
def duration(path):
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout
    return float(out.strip() or 0)


def scene_cuts(path, thr):
    r = _run([FFMPEG, "-hide_banner", "-i", path, "-an", "-vf", f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"])
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def frame_signal(path, fps=10):
    p = subprocess.run([FFMPEG, "-loglevel", "error", "-i", path, "-an", "-vf", f"fps={fps},scale=64:36,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(a) // (64 * 36)
    return a[: n * 64 * 36].reshape(n, 36, 64).astype(np.float32) / 255, fps


def _peaks(sig, thr, min_gap):
    idx = []
    for i in range(1, len(sig) - 1):
        if sig[i] >= thr and sig[i] >= sig[i - 1] and sig[i] >= sig[i + 1]:
            if idx and i - idx[-1] < min_gap:
                if sig[i] > sig[idx[-1]]:
                    idx[-1] = i
                continue
            idx.append(i)
    return idx


def detect_shots(path, dur):
    """Hard cuts: ffmpeg scene score + frame-difference peaks. Soft cuts (dissolves / big animated
    transitions): peaks of the 0.5s-apart difference. Both use adaptive (median + k*MAD) thresholds."""
    thr = 0.3
    cuts = scene_cuts(path, thr)
    fr, fps = frame_signal(path)
    if len(fr) > 4:
        d1 = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
        med, mad = np.median(d1), np.median(np.abs(d1 - np.median(d1))) + 1e-4
        for i in _peaks(d1, max(0.03, med + 8 * mad), fps // 2):
            cuts.append((i + 1) / fps)
        k = fps // 2
        if len(fr) > k + 2:
            dl = np.abs(fr[k:] - fr[:-k]).mean(axis=(1, 2))
            med2, mad2 = np.median(dl), np.median(np.abs(dl - np.median(dl))) + 1e-4
            for i in _peaks(dl, max(0.028, med2 + 4 * mad2), int(fps * 1.5)):
                cuts.append((i + k / 2) / fps)
    pts, last = [0.0], 0.0
    for c in sorted(cuts):
        if c - last >= 0.5 and dur - c >= 0.3:
            pts.append(c)
            last = c
    pts.append(dur)
    return [(round(pts[i], 2), round(pts[i + 1], 2)) for i in range(len(pts) - 1)], "scene>0.3 + 帧差自适应阈值"


def grab(path, t, dst=None, w=320):
    args = [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{max(t,0):.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={w}:-2"]
    if dst:
        _run(args + ["-q:v", "4", dst])
        return dst
    r = subprocess.run(args + ["-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    from io import BytesIO
    return Image.open(BytesIO(r.stdout)) if r.stdout else None


def phase_shift(a, b):
    A = np.fft.fft2(a); B = np.fft.fft2(b)
    R = A * np.conj(B); R /= np.abs(R) + 1e-9
    r = np.abs(np.fft.ifft2(R))
    y, x = np.unravel_index(np.argmax(r), r.shape)
    h, w = a.shape
    if y > h // 2: y -= h
    if x > w // 2: x -= w
    return x, y, float(r.max())


def motion(path, s, e):
    d = e - s
    t1, t2 = s + d * 0.2, s + d * 0.8
    f1, f2 = grab(path, t1, w=160), grab(path, t2, w=160)
    if f1 is None or f2 is None:
        return {"camera": "未知", "change": 0}
    g1 = np.asarray(f1.convert("L"), dtype=np.float32); g2 = np.asarray(f2.convert("L"), dtype=np.float32)
    h = min(g1.shape[0], g2.shape[0]); g1, g2 = g1[:h], g2[:h]
    change = float(np.mean(np.abs(g1 - g2)) / 255)
    dx, dy, peak = phase_shift(g1 - g1.mean(), g2 - g2.mean())
    # zoom: compare center crop energy ratio via edge density
    def edges(g):
        return np.mean(np.abs(np.diff(g, axis=1)))
    c1, c2 = edges(g1[h//4:3*h//4, 40:120]), edges(g2[h//4:3*h//4, 40:120])
    if change < 0.02:
        cam = "固定 / 静帧"
    elif abs(dx) >= 4 and abs(dx) >= abs(dy):
        cam = "横移 / 摇镜（向" + ("左" if dx > 0 else "右") + "）"
    elif abs(dy) >= 4:
        cam = "竖移 / 升降（向" + ("上" if dy > 0 else "下") + "）"
    elif change > 0.12:
        cam = "画面内大幅变化（动画 / 转场 / 主体运动）"
    elif abs(c2 - c1) / (c1 + 1e-6) > 0.15:
        cam = "推近" if c2 < c1 else "拉远"
    else:
        cam = "轻微运动 / 缓推"
    return {"camera": cam, "change": round(change, 3)}


def look(img):
    a = np.asarray(img.convert("RGB").resize((64, 36)), dtype=np.float32)
    lum = float((0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).mean() / 255)
    q = (a // 64).astype(int).reshape(-1, 3)
    keys, counts = np.unique(q[:, 0] * 16 + q[:, 1] * 4 + q[:, 2], return_counts=True)
    top = keys[np.argsort(-counts)][:3]
    pal = ["#%02x%02x%02x" % (int((k // 16) * 64 + 32), int(((k // 4) % 4) * 64 + 32), int((k % 4) * 64 + 32)) for k in top]
    return round(lum, 2), pal


def ocr(path_img):
    if not TESS:
        return ""
    langs = "eng"
    have = _run([TESS, "--list-langs"]).stdout
    if "chi_sim" in have:
        langs = "eng+chi_sim"
    txt = _run([TESS, path_img, "-", "-l", langs, "--psm", "11"]).stdout
    words = [w for w in re.split(r"\s+", txt) if len(w) >= 2 and re.search(r"[A-Za-z\u4e00-\u9fff]{2,}", w)]
    return " ".join(words)[:160]


# ------------------------------------------------------------------ audio
def audio(path, dur, cuts):
    r = _run([FFMPEG, "-hide_banner", "-i", path, "-vn", "-ac", "1", "-ar", "11025", "-f", "s16le", "-"], timeout=300) if False else None
    p = subprocess.run([FFMPEG, "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", "11025", "-f", "s16le", "-"], capture_output=True)
    if not p.stdout:
        return {"has_audio": False, "summary": "无音轨（静音视频）"}
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768
    if len(x) < 11025:
        return {"has_audio": False, "summary": "音轨过短"}
    hop = 256
    n = len(x) // hop
    env = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1))
    rms_db = 20 * np.log10(np.mean(env) + 1e-9)
    silent = float(np.mean(env < 0.005))
    on = np.maximum(np.diff(env), 0)
    on = on - on.mean()
    fps = 11025 / hop
    ac = np.correlate(on, on, mode="full")[len(on) - 1:]
    lo, hi = int(fps * 60 / 180), int(fps * 60 / 70)
    bpm, conf, aligned = None, 0.0, None
    if hi < len(ac) and ac[0] > 0:
        lag = lo + int(np.argmax(ac[lo:hi]))
        conf = float(ac[lag] / ac[0])
        if conf > 0.08:
            bpm = round(60 * fps / lag)
            beat = 60.0 / bpm
            # beat phase from onset peaks
            ph = np.arange(0, beat, 0.01)
            idx = (np.arange(len(on)) / fps)
            score = [on[((idx - p0) % beat) < 0.03].sum() for p0 in ph]
            p0 = ph[int(np.argmax(score))]
            inner = [c for c in cuts if 0.3 < c < dur - 0.3]
            if inner:
                hits = [min((c - p0) % beat, beat - (c - p0) % beat) <= 0.08 for c in inner]
                aligned = round(100 * sum(hits) / len(hits))
    # zero-crossing rate as a voice/music hint
    zcr = float(np.mean(np.abs(np.diff(np.sign(x[: 11025 * 30])))) / 2)
    parts = [f"平均响度约 {rms_db:.0f} dBFS", f"静音占比 {silent*100:.0f}%"]
    if bpm:
        parts.append(f"节拍估计约 {bpm} BPM（置信度 {conf:.2f}，仅供参考）")
        if aligned is not None:
            parts.append(f"{aligned}% 的切点落在节拍 ±80ms 内")
    else:
        parts.append("未检测到稳定节拍（可能以旁白 / 环境声为主）")
    return {"has_audio": True, "rms_db": round(rms_db, 1), "silence_ratio": round(silent, 2), "bpm": bpm,
            "bpm_confidence": round(conf, 2), "cuts_on_beat_pct": aligned, "zcr": round(zcr, 3), "summary": "；".join(parts)}


# ------------------------------------------------------------------ structure & summary
def structure(shots, dur):
    segs = []
    def add(name, s, e, note):
        if e > s:
            segs.append({"part": name, "start": round(s, 1), "end": round(e, 1), "note": note})
    hook_end = next((e for s, e in shots if e >= min(3.0, dur * 0.12)), min(3, dur))
    end_start = shots[-1][0] if len(shots) > 1 and dur - shots[-1][0] <= max(6, dur * 0.2) else dur * 0.88
    reveal_end = min(end_start, max(hook_end, dur * 0.25))
    add("Hook", 0, hook_end, "开场 / 首帧（缩略图），决定停留")
    add("Reveal / 主张", hook_end, reveal_end, "引出产品或核心主张")
    add("Features / 展示", reveal_end, end_start, "功能 / 场景展示主体")
    add("CTA / 收尾", end_start, dur, "最后一个镜头：logo、tagline 或行动号召")
    return segs


def techniques(res):
    t, sh, dur = [], res["shots"], res["duration"]
    asl = res["pacing"]["avg_shot_s"]
    t.append(f"共 {len(sh)} 个镜头，平均镜头长 {asl:.1f}s —— " + ("快切节奏，适合信息流抓注意力" if asl < 2 else "中等节奏，每个镜头讲一件事" if asl < 4.5 else "长镜头为主，靠镜头内动画或表演推进"))
    first = sh[0]
    t.append(f"首个镜头 {first['duration']:.1f}s、亮度 {first['brightness']:.2f}" + ("，首帧偏暗，注意缩略图可读性" if first['brightness'] < 0.15 else "，首帧本身可作缩略图"))
    last = sh[-1]
    t.append(f"结尾镜头停留 {last['duration']:.1f}s" + ("，给 logo / CTA 留足阅读时间" if last['duration'] >= 2 else "，收尾很短，适合循环播放"))
    darks = [s for s in sh if s["brightness"] < 0.2]
    if darks and len(darks) < len(sh):
        t.append(f"有 {len(darks)} 个暗场景镜头（如 {darks[0]['start']:.1f}s 处），用明暗切换分章节 / 重新抓注意力")
    moves = {}
    for s in sh:
        moves[s["camera"]] = moves.get(s["camera"], 0) + 1
    top = sorted(moves.items(), key=lambda kv: -kv[1])[:2]
    t.append("运镜以「" + "」「".join(k for k, _ in top) + "」为主（基于帧间位移估计）")
    a = res["audio"]
    if a.get("bpm") and a.get("cuts_on_beat_pct") is not None:
        t.append(f"音乐约 {a['bpm']} BPM，{a['cuts_on_beat_pct']}% 切点卡在拍上" + ("，剪辑明显跟拍" if a['cuts_on_beat_pct'] >= 50 else "，剪辑没有严格卡拍"))
    elif not a.get("has_audio"):
        t.append("无音轨：全程靠画面和文字讲清，静音可看懂")
    texts = [s for s in sh if s.get("text")]
    if texts:
        t.append(f"{len(texts)} 个镜头检测到屏幕文字（OCR），文字是叙事主线的一部分")
    return t


def vision(res, case):
    key = os.environ.get("CASELIB_LLM_API_KEY")
    if not key:
        return None
    base = os.environ.get("CASELIB_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("CASELIB_LLM_MODEL", "gpt-4o-mini")
    shots = res["shots"][:30]
    content = [{"type": "text", "text": (
        "你是资深广告剪辑师。下面是一支视频按镜头切分后的关键帧（每张标注镜头编号和时间码）。"
        f"视频标题：{case.get('title')}。请只返回 JSON："
        '{"shots":[{"i":镜头编号,"shot_type":"景别(特写/近景/中景/全景/远景/界面/文字卡)","camera":"运镜","desc":"画面一句话","text":"屏幕上的文字(没有则空)"}],'
        '"structure":[{"part":"Hook|Reveal|Features|Proof|CTA","start":秒,"end":秒,"note":"一句话"}],"techniques":["可借鉴的手法，5-8 条，中文"],"music":"音乐/声音判断(若能从画面推断)"}')}]
    for s in shots:
        p = os.path.join(res["_dir"], os.path.basename(s["keyframe"]))
        content.append({"type": "text", "text": f"镜头 {s['i']}：{s['start']:.1f}s–{s['end']:.1f}s"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()}})
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}],
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.load(r)
        out = json.loads(j["choices"][0]["message"]["content"])
        out["model"] = model
        return out
    except Exception as e:
        return {"error": str(e)[:300], "model": model}


def analyze(case, force=False):
    vp = ensure_video(case)
    if not vp:
        raise ValueError("拿不到这条视频的文件，无法分析（原视频可能已删除或需要登录）")
    od = out_dir(case)
    cp = cache_path(case)
    if os.path.exists(cp) and not force:
        return json.load(open(cp, encoding="utf-8"))
    os.makedirs(od, exist_ok=True)
    t0 = time.time()
    dur = duration(vp)
    shots, thr = detect_shots(vp, dur)
    rel = "/" + os.path.relpath(od, store.ROOT)
    out = []
    for i, (s, e) in enumerate(shots, 1):
        kf = os.path.join(od, f"shot_{i:03d}.jpg")
        grab(vp, s + (e - s) * 0.5, kf, w=480)
        img = Image.open(kf)
        lum, pal = look(img)
        m = motion(vp, s, e)
        out.append({"i": i, "start": s, "end": e, "duration": round(e - s, 2), "keyframe": f"{rel}/shot_{i:03d}.jpg",
                    "brightness": lum, "palette": pal, "camera": m["camera"], "change": m["change"],
                    "text": ocr(kf), "shot_type": None, "desc": None})
    lens = [x["duration"] for x in out]
    third = dur / 3
    def cpm(a, b):
        return round(sum(1 for x in out[1:] if a <= x["start"] < b) / max((b - a), 1e-6) * 10, 1)
    pacing = {"shots": len(out), "avg_shot_s": round(float(np.mean(lens)), 2), "median_shot_s": round(float(np.median(lens)), 2),
              "shortest_s": round(min(lens), 2), "longest_s": round(max(lens), 2),
              "cuts_per_10s": round((len(out) - 1) / dur * 10, 1) if dur else 0,
              "cuts_per_10s_by_third": [cpm(0, third), cpm(third, 2 * third), cpm(2 * third, dur + 0.01)],
              "scene_threshold": thr}
    res = {"version": VERSION, "case_id": case["id"], "duration": round(dur, 2), "shots": out, "pacing": pacing,
           "audio": audio(vp, dur, [x["start"] for x in out]), "_dir": od}
    res["structure"] = structure(shots, dur)
    res["techniques"] = techniques(res)
    res["ocr"] = bool(TESS)
    v = vision(res, case)
    res["vision"] = v
    if v and not v.get("error"):
        byi = {x.get("i"): x for x in v.get("shots", [])}
        for s in out:
            vs = byi.get(s["i"]) or {}
            s["shot_type"] = vs.get("shot_type")
            s["desc"] = vs.get("desc")
            if vs.get("camera"):
                s["camera_llm"] = vs.get("camera")
            if vs.get("text") and not s["text"]:
                s["text"] = vs.get("text")
        if v.get("structure"):
            res["structure"] = v["structure"]
            res["structure_source"] = "vision"
        if v.get("techniques"):
            res["techniques"] = v["techniques"] + ["—— 结构化数据 ——"] + res["techniques"]
    res.pop("_dir")
    res["structure_source"] = res.get("structure_source", "heuristic")
    res["generated_at"] = store.now_iso()
    res["elapsed_s"] = round(time.time() - t0, 1)
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    return res


if __name__ == "__main__":
    cid = sys.argv[1]
    case = next(c for c in store.load_cases() if c["id"] == cid)
    r = analyze(case, force="--force" in sys.argv)
    print(json.dumps({k: r[k] for k in ("duration", "pacing", "audio", "structure", "techniques")}, ensure_ascii=False, indent=1, default=float))
