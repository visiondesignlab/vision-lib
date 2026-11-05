"""Resolve X originals and cache playable media / real author avatars for ingestion."""
import copy
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import mediautil
import store


def post_id(url):
    parsed = urllib.parse.urlparse(url or "")
    if parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        return None
    match = re.search(r"/status(?:es)?/(\d+)", parsed.path)
    return match.group(1) if match else None


def read_json(url, user_agent=mediautil.UA):
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, context=mediautil.https_context(), timeout=25) as response:
        return json.load(response)


def resolve_post(url, *, official_only=False):
    """Prefer X's public embed metadata; an X reader is only a fallback."""
    pid = post_id(url)
    if not pid:
        raise ValueError("Not an X post URL")
    try:
        from yt_dlp.extractor.twitter import TwitterIE
        token = TwitterIE()._generate_syndication_token(pid)
        endpoint = "https://cdn.syndication.twimg.com/tweet-result?" + urllib.parse.urlencode({"id": pid, "token": token})
        data = read_json(endpoint, "Googlebot")
        user = data.get("user") or {}
        if not user.get("screen_name"):
            raise ValueError("X embed metadata unavailable")
        variants = []
        for item in data.get("mediaDetails") or []:
            variants += (item.get("video_info") or {}).get("variants") or []
        return {"author": user["screen_name"], "text": data.get("text") or "", "avatar": user.get("profile_image_url_https"),
                "date": data.get("created_at"), "metrics": {"likes": data.get("favorite_count"), "replies": data.get("conversation_count")},
                "variants": variants, "provider": "X", "fetched_at": store.now_iso()}
    except Exception as original_error:
        if official_only:
            raise ValueError("无法读取 X 原帖") from original_error
        data = read_json("https://api.fxtwitter.com/status/" + pid)
        tweet = data.get("tweet") or {}
        user = tweet.get("author") or {}
        if not user.get("screen_name"):
            raise ValueError(f"X post unavailable: {pid}") from original_error
        videos = (tweet.get("media") or {}).get("videos") or []
        return {"author": user["screen_name"], "avatar": user.get("avatar_url"),
                "date": tweet.get("created_at"), "metrics": {"likes": tweet.get("likes"), "replies": tweet.get("replies"),
                    "views": tweet.get("views"), "reposts": tweet.get("retweets"), "bookmarks": tweet.get("bookmarks")},
                "variants": [{"url": v.get("url"), "bitrate": 0} for v in videos],
                "provider": "FxTwitter", "fetched_at": store.now_iso()}


def cache_avatar(url):
    if not url or urllib.parse.urlparse(url).hostname != "pbs.twimg.com" or "/profile_images/" not in url:
        return ""
    from PIL import Image
    large = re.sub(r"_normal(?=\.)", "_200x200", url)
    for candidate in dict.fromkeys([large, url]):
        suffix = Path(urllib.parse.urlparse(candidate).path).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return ""
        folder = Path(store.MEDIA) / "avatars"
        folder.mkdir(exist_ok=True)
        name = hashlib.sha256(candidate.encode()).hexdigest()[:20] + suffix
        dst = folder / name
        if dst.exists():
            return "/media/avatars/" + name
        fd, tmp = tempfile.mkstemp(dir=folder, suffix=suffix)
        os.close(fd)
        try:
            mediautil.http_download(candidate, tmp, timeout=25)
            with Image.open(tmp) as image:
                image.verify()
            os.replace(tmp, dst)
            return "/media/avatars/" + name
        except Exception:
            continue
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return ""


def playable(media):
    return all((media.get(k) or "").startswith("/media/") and
               (Path(store.ROOT) / media[k].lstrip("/")).is_file() and
               (Path(store.ROOT) / media[k].lstrip("/")).stat().st_size > 0
               for k in ("video", "preview"))


def video_urls(metadata, fallback=""):
    def height(v):
        match = re.search(r"/(\d+)x(\d+)/", v.get("url") or "")
        return min(int(match[1]), int(match[2])) if match else 0
    variants = [v for v in metadata.get("variants") or []
                if urllib.parse.urlparse(v.get("url") or "").hostname == "video.twimg.com"
                and urllib.parse.urlparse(v.get("url") or "").path.endswith(".mp4")]
    # A post can contain several videos. Match the discovered video before choosing its quality.
    expected = re.search(r"/(?:amplify_video|ext_tw_video|tweet_video)/([^/]+)/", fallback)
    if expected:
        matches = [v for v in variants if "/" + expected[1] + "/" in v["url"]]
        variants = matches
    limited = [v for v in variants if height(v) <= 1080]
    variants = sorted(limited or variants, key=lambda v: (height(v), v.get("bitrate") or 0), reverse=True)
    urls = [v["url"] for v in variants]
    if urllib.parse.urlparse(fallback).hostname == "video.twimg.com":
        urls.append(fallback)
    return list(dict.fromkeys(urls))


def cache_video(case, metadata):
    media = case.get("media") or {}
    if playable(media):
        return media
    # Use the same MP4 / hover-preview pipeline as the video-case collection.
    with tempfile.TemporaryDirectory(prefix="vision-lib-x-") as temporary:
        src = None
        for url in video_urls(metadata, media.get("remote_video") or "")[:3]:
            try:
                candidate = mediautil.http_download(url, os.path.join(temporary, "source.mp4"), timeout=120)
                info = mediautil.probe(candidate)
                if info.get("width") and info.get("height") and info.get("duration"):
                    src = candidate
                    break
            except Exception:
                continue
        if not src:
            src = mediautil.ytdlp_download(case["source"]["url"], os.path.join(temporary, "source"), timeout=180)
        if not src:
            # Already downloaded source files are safe to reuse; never replace with unrelated media.
            previous = Path(store.MEDIA) / case["id"] / "src.mp4"
            if previous.is_file() and mediautil.probe(str(previous)).get("width"):
                src = str(previous)
        if not src:
            raise ValueError("原帖视频暂时无法下载")
        return mediautil.process_video(src, case["id"])


def enrich(case, metadata=None, with_video=True):
    case = copy.deepcopy(case)
    source = case.setdefault("source", {})
    # Keep discovery provenance internally; it is not the video's author or public source.
    if source.get("via") == "launchvideos.gallery":
        case["discovery"] = {"site": source.pop("via"), "url": source.pop("via_url", ""),
                             "reported_metrics": source.pop("metrics", {}),
                             "reported_at": source.pop("metrics_fetched_at", "")}
        case["tags"] = [t for t in case.get("tags") or [] if t != "launchvideos.gallery"]
    errors = []
    if metadata is None:
        try:
            metadata = resolve_post(source.get("url"))
        except Exception as e:
            metadata = {}
            errors.append(str(e))
    if metadata.get("author"):
        source.update(platform="X", author="@" + metadata["author"], author_url="https://x.com/" + metadata["author"])
        source["avatar"] = cache_avatar(metadata.get("avatar"))
        source["avatar_source_url"] = metadata.get("avatar") or ""
        metrics = {k: v for k, v in metadata.get("metrics", {}).items() if v is not None}
        if metrics and not source.get("metrics"):
            source["metrics"] = metrics
            source["metrics_fetched_at"] = metadata["fetched_at"]
        if metadata.get("date"):
            try:
                source["date"] = datetime.fromisoformat(metadata["date"].replace("Z", "+00:00")).astimezone(store.CST).strftime("%Y-%m-%d %H:%M（北京时间）")
            except ValueError:
                pass
    if with_video and not playable(case.get("media") or {}):
        try:
            case["media"] = cache_video(case, metadata)
        except Exception as e:
            errors.append(str(e))
    case["updated_at"] = store.now_iso()
    return case, errors
