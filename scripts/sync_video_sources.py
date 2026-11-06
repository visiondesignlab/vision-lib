#!/usr/bin/env python3
"""Refresh original-site MP4 URLs without downloading or uploading videos."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mediautil
import store
import xsource


def sync(refresh=False):
    path = ROOT / 'catalog/video-sources.json'
    data = json.loads(path.read_text()) if path.exists() else {'sources': {}}
    sources = data['sources']
    cases = [c for c in store.load_cases() if c.get('status') == 'published'
             and c.get('media', {}).get('kind') == 'video' and xsource.post_id(c.get('source', {}).get('url'))]
    pending = [c for c in cases if refresh or c['source']['url'] not in sources]

    def resolve(case):
        source = case['source']['url']
        metadata = xsource.resolve_post(source, official_only=True)
        # Preserve the selected original if a post contains multiple videos.
        previous = sources.get(source, {}).get('video', '')
        variants = xsource.video_urls(metadata, previous)
        if not variants:
            raise ValueError('原帖没有可用的视频地址')
        url = variants[0]
        request = urllib.request.Request(url, headers={'Range':'bytes=0-31', 'User-Agent':mediautil.UA})
        with urllib.request.urlopen(request, context=mediautil.https_context(), timeout=25) as response:
            if response.status not in (200, 206) or not response.headers.get('Content-Type', '').startswith('video/'):
                raise ValueError('原站未返回视频')
            response.read(32)
        return source, {'video':url, 'checked_at':datetime.now(timezone.utc).isoformat()}

    failed = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(resolve, case):case for case in pending}
        for job in as_completed(jobs):
            try:
                source, value = job.result()
                sources[source] = value
            except Exception as error:
                failed.append({'id':jobs[job]['id'], 'error':str(error)})
    # Write atomically so local readers never see a partially written catalog.
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps({'resolved':len(sources), 'attempted':len(pending), 'failed':failed}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true', help='Also refresh existing source URLs')
    sync(parser.parse_args().refresh)
