"""Media helpers: download with yt-dlp / HTTP, transcode with ffmpeg, make thumbnails."""
import json, os, shutil, ssl, subprocess, tempfile, urllib.request
from store import MEDIA

def media_binary(name):
    # launchd starts with a minimal PATH even when Homebrew is installed.
    return shutil.which(name) or shutil.which(name, path='/opt/homebrew/bin:/usr/local/bin') or name


FFMPEG = media_binary("ffmpeg")
FFPROBE = media_binary("ffprobe")
YTDLP = shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")
UA = "Mozilla/5.0 (caselib ingest)"


def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", path],
                         capture_output=True, text=True).stdout
    j = json.loads(out or "{}")
    st = (j.get("streams") or [{}])[0]
    return {"width": st.get("width"), "height": st.get("height"),
            "duration": round(float((j.get("format") or {}).get("duration") or 0), 1)}


def _ff(args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-filter_threads", "2"] + args[:-1] + ["-threads", "2", args[-1]], check=True, timeout=600)


def _ff_atomic(args):
    """Publish a complete output only after FFmpeg succeeds."""
    dst = args[-1]
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dst), suffix=os.path.splitext(dst)[1])
    os.close(fd)
    try:
        _ff(args[:-1] + [tmp])
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def process_video(src, case_id, thumb_at=None):
    """src: local mp4. Writes media/<id>/{web.mp4,preview.mp4,thumb.jpg}; returns media dict."""
    d = os.path.join(MEDIA, case_id)
    os.makedirs(d, exist_ok=True)
    info = probe(src)
    dur = info["duration"] or 1
    web, prev, thumb = (os.path.join(d, n) for n in ("web.mp4", "preview.mp4", "thumb.jpg"))
    scale = "scale='min(1920,iw)':-2"
    if (info["height"] or 0) > (info["width"] or 0):
        scale = "scale=-2:'min(1920,ih)'"
    if not os.path.exists(web):
      _ff_atomic(["-i", src, "-vf", scale, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", web])
    if not os.path.exists(prev):
      _ff_atomic(["-i", src, "-t", str(min(8, dur)), "-vf", "scale=480:-2", "-an", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart", prev])
    t = thumb_at if thumb_at is not None else min(dur * 0.25, 6)
    if not os.path.exists(thumb):
      _ff_atomic(["-ss", str(t), "-i", src, "-frames:v", "1", "-vf", "scale=720:-2", "-q:v", "4", thumb])
    base = "/media/" + case_id + "/"
    return {"kind": "video", "video": base + "web.mp4", "preview": base + "preview.mp4",
            "thumbnail": base + "thumb.jpg", "images": [],
            "specs": {"duration_s": info["duration"], "resolution": f"{info['width']}×{info['height']}"}}


def process_images(paths, case_id):
    d = os.path.join(MEDIA, case_id)
    os.makedirs(d, exist_ok=True)
    out = []
    for i, p in enumerate(paths):
        dst = os.path.join(d, f"img{i}.jpg")
        _ff(["-i", p, "-vf", "scale='min(1600,iw)':-2", "-q:v", "3", dst])
        out.append("/media/" + case_id + f"/img{i}.jpg")
    if out:
        _ff(["-i", paths[0], "-vf", "scale=720:-2", "-q:v", "4", os.path.join(d, "thumb.jpg")])
    return {"kind": "images", "images": out, "thumbnail": "/media/" + case_id + "/thumb.jpg" if out else "",
            "video": "", "preview": ""}


def http_download(url, dst, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=https_context()) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)
    return dst


def https_context():
    # Python.org's macOS install may not include the system certificate bundle.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def ytdlp_download(url, dst_noext, timeout=300):
    """Returns path of downloaded mp4 or None."""
    cmd = [YTDLP, "-q", "--no-warnings", "--no-playlist", "-f", "best[ext=mp4][height<=1080]/best[height<=1080]/best",
           "--max-filesize", "200M", "-o", dst_noext + ".%(ext)s", url]
    try:
        subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    except Exception:
        return None
    for ext in ("mp4", "webm", "mov", "mkv"):
        p = dst_noext + "." + ext
        if os.path.exists(p):
            return p
    return None


def placeholder_thumb(case_id, title, sub=""):
    """A plain text card when no media exists (never pretends to be a frame of the source)."""
    from PIL import Image, ImageDraw, ImageFont
    d = os.path.join(MEDIA, case_id)
    os.makedirs(d, exist_ok=True)
    img = Image.new("RGB", (720, 405), (238, 240, 243))
    dr = ImageDraw.Draw(img)
    font = None
    for fp in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
               "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"):
        if os.path.exists(fp):
            font = fp
            break
    big = ImageFont.truetype(font, 40, index=2) if font else ImageFont.load_default()
    small = ImageFont.truetype(font, 22, index=2) if font else ImageFont.load_default()
    dr.text((40, 150), title[:22], fill=(30, 32, 36), font=big)
    if sub:
        dr.text((40, 215), sub[:40], fill=(110, 115, 125), font=small)
    p = os.path.join(d, "thumb.jpg")
    img.save(p, quality=88)
    return "/media/" + case_id + "/thumb.jpg"
