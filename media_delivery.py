"""Public playback uses original online sources; local originals stay private."""
import json
from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def provider(url):
    parts = urlsplit(url or '')
    if parts.scheme != 'https':
        return None
    host = parts.hostname
    if host in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com'):
        match = re.fullmatch(r'/[^/]+/status/(\d+)(?:/video/\d+)?/?', parts.path)
        return ('x', match[1]) if match else None
    if host in ('youtube.com', 'www.youtube.com', 'youtu.be', 'vimeo.com', 'player.vimeo.com'):
        return ('online', url)


@lru_cache(maxsize=1)
def _sources(path, modified):
    return json.loads(Path(path).read_text()).get('sources', {})


def online_media(case):
    media = dict(case.get('media') or {})
    source = (case.get('source') or {}).get('url', '')
    if media.get('kind') != 'video' or not provider(source):
        return media
    catalog = ROOT / 'catalog/video-sources.json'
    sources = _sources(str(catalog), catalog.stat().st_mtime_ns) if catalog.exists() else {}
    remote = sources.get(source, {}).get('video', '')
    if not remote:
        candidate = media.get('remote_video') or ''
        if urlsplit(candidate).scheme == 'https' and urlsplit(candidate).hostname == 'video.twimg.com':
            remote = candidate
    # Never publish the cached original/hover video for a supported online source.
    media.pop('video', None)
    media.pop('preview', None)
    media.pop('remote_video', None)
    media['embed'] = 'remote'
    if remote:
        media['video'] = remote
        media['preview'] = remote
    return media


def excluded_backups(root):
    path = Path(root) / 'catalog/external-assets.json'
    return set(json.loads(path.read_text())) if path.exists() else set()


def online_references(value, replacements):
    """Attachments can point at the same cached video as the player."""
    if isinstance(value, dict):
        return {key: online_references(child, replacements) for key, child in value.items()}
    if isinstance(value, list):
        return [online_references(child, replacements) for child in value]
    return replacements.get(value, value) if isinstance(value, str) else value
