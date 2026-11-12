#!/usr/bin/env python3
"""Read an Eagle library; publish source-verified groups through the CMS lifecycle.

Scan is read-only. --apply requires an editorial manifest with original-post
evidence. Internal source paths and mappings remain in ignored output files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cms_content
import mediautil
import store

IMAGES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
VIDEOS = {'mp4', 'mov', 'webm'}


def require_local(path):
    # macOS can report a file's size while its content is only in iCloud.
    # Opening it would synchronously wait for FileProvider to download it.
    if getattr(Path(path).stat(), 'st_flags', 0) & getattr(stat, 'SF_DATALESS', 0x40000000):
        raise OSError('iCloud content is not downloaded locally: ' + str(path))


def digest(path):
    require_local(path)
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_key(url):
    parsed = urlsplit(url or '')
    host = (parsed.hostname or '').lower().removeprefix('www.')
    path = parsed.path.rstrip('/')
    if host in {'x.com', 'twitter.com', 'mobile.twitter.com'}:
        match = re.search(r'/status(?:es)?/(\d+)', path)
        if match:
            return 'x.com/status/' + match[1]
    if host == 'instagram.com':
        match = re.search(r'/(?:reel|reels|p)/([^/]+)', path)
        if match:
            return 'instagram.com/p/' + match[1]
    if host in {'threads.net', 'threads.com'}:
        match = re.search(r'/post/([^/]+)', path)
        if match:
            return 'threads.com/post/' + match[1]
        host = 'threads.com'
    return host + path


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def scan(library):
    library = Path(library).resolve()
    if not (library / 'metadata.json').is_file():
        raise ValueError('Eagle library metadata is unavailable')
    items, failures = [], []
    for metadata in sorted((library / 'images').glob('*.info/metadata.json')):
        try:
            require_local(metadata)
            data = json.loads(metadata.read_text())
            if data.get('isDeleted'):
                continue
            ext = data['ext'].lower()
            if ext not in IMAGES | VIDEOS:
                raise ValueError('Unsupported asset format: ' + ext)
            if not data.get('url'):
                raise ValueError('Missing original source URL')
            cms_content.safe_url(data['url'])
            path = (metadata.parent / (data['name'] + '.' + data['ext'])).resolve()
            if not path.is_relative_to(library) or not path.is_file():
                raise ValueError('Source asset is unavailable')
            items.append({'id': data['id'], 'name': data['name'], 'path': str(path),
                          'kind': 'video' if ext in VIDEOS else 'image', 'ext': ext,
                          'url': data['url'], 'sourceKey': source_key(data['url']),
                          'sha256': digest(path), 'metadataSha256': digest(metadata),
                          'addedAt': data.get('btime', 0)})
        except (ValueError, KeyError, OSError) as error:
            failures.append({'metadata': str(metadata), 'error': str(error)})
    items.sort(key=lambda item: (item['addedAt'], item['id']))
    return {'library': str(library), 'checkedAt': store.now_iso(), 'complete': not failures,
            'items': items, 'failures': failures}


def copy_media(items, key):
    folder = Path(store.MEDIA) / ('eagle-' + hashlib.sha256(key.encode()).hexdigest()[:16])
    folder.mkdir(parents=True, exist_ok=True)
    media_items = []
    for item in items:
        source = Path(item['path'])
        if digest(source) != item['sha256']:
            raise ValueError('Eagle asset changed during import: ' + item['id'])
        filename = item['id'] + '-' + item['sha256'][:10] + '.' + item['ext']
        target = folder / filename
        if not target.exists():
            shutil.copy2(source, target)
        if digest(target) != item['sha256']:
            raise ValueError('Copied media checksum mismatch')
        entry = {'kind': item['kind'], 'url': '/media/' + folder.name + '/' + filename}
        if item['kind'] == 'video':
            info = mediautil.probe(str(target))
            if not info.get('width') or not info.get('duration'):
                raise ValueError('Video is not playable: ' + item['id'])
            thumbnail = target.with_suffix('.jpg')
            if not thumbnail.exists():
                subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(min(1, info['duration']/2)),
                                '-i', str(target), '-frames:v', '1', '-vf', 'scale=1280:-2',
                                '-q:v', '3', '-y', str(thumbnail)], check=True)
            entry['thumbnail'] = '/media/' + folder.name + '/' + thumbnail.name
        else:
            from PIL import Image
            with Image.open(target) as image:
                image.verify()
        media_items.append(entry)
    first = media_items[0]
    media = {'kind': 'video' if len(items) == 1 and first['kind'] == 'video' else 'images',
             'thumbnail': first.get('thumbnail', first['url'])}
    if media['kind'] == 'video':
        media['video'] = first['url']
        info = mediautil.probe(str(folder / Path(first['url']).name))
        media['specs'] = {'resolution': f"{info['width']}×{info['height']}", 'duration_s': info['duration']}
    elif all(item['kind'] == 'image' for item in items):
        media['images'] = [item['url'] for item in media_items]
    else:
        media['items'] = media_items
    return media


def apply_manifest(inventory, manifest, state_path):
    if inventory.get('failures') or inventory.get('complete') is False:
        return [{'sourceKey': source_key(group['sourceUrl']), 'status': 'failed',
                 'error': 'Source scan is incomplete; preserve existing CMS media and retry after source files are available.'}
                for group in manifest['groups']]
    state = json.loads(state_path.read_text()) if state_path.exists() else {'version': 1, 'groups': {}}
    lookup = {item['id']: item for item in inventory['items']}
    result = []
    for group in manifest['groups']:
        key = source_key(group['sourceUrl'])
        try:
            ordered = [lookup[item_id] for item_id in group['eagleIds']]
            seen = set()
            items = [item for item in ordered if item['sha256'] not in seen and not seen.add(item['sha256'])]
            if not items or len(items) > 30:
                raise ValueError('A source group must contain 1–30 distinct assets')
            hashes = {item['id']: item['sha256'] for item in ordered}
            aliases = {key, *(source_key(item['url']) for item in ordered)}
            existing = [c for c in store.load_cases() if source_key(c.get('source', {}).get('url')) in aliases]
            previous = state['groups'].get(key)
            if len(existing) > 1:
                raise ValueError('Multiple existing CMS records for this source; preserve them for reconciliation')
            rejected = set(store.load_rejected())
            if any(store.norm_url(url) in rejected for url in [group['sourceUrl'], *(item['url'] for item in ordered)]):
                result.append({'sourceKey': key, 'status': 'skipped_rejected'})
                continue
            if existing and previous and previous.get('ownership') == 'eagle' and not previous.get('publishedAt') and previous.get('hashes') == hashes:
                current = cms_content.admin_view(existing[0])
                if current['status'] == 'draft':
                    current = cms_content.change(current['id'], 'submit', {'_version': current['_version']})
                if current['status'] == 'pending':
                    current = cms_content.change(current['id'], 'approve', {'_version': current['_version']})
                if current['status'] != 'published':
                    raise ValueError('Interrupted import no longer has a publishable status')
                previous['publishedAt'] = current['published_at']
                save(state_path, state)
                result.append({'sourceKey': key, 'status': 'published', 'cmsId': current['id'], 'resumed': True})
                continue
            if existing and (not previous or previous.get('ownership') != 'eagle' or previous.get('hashes') == hashes):
                state['groups'][key] = {**(previous or {}), 'cmsId': existing[0]['id'], 'hashes': hashes,
                                        'aliases': sorted(aliases), 'ownership': (previous or {}).get('ownership', 'existing'),
                                        'checkedAt': store.now_iso()}
                save(state_path, state)
                result.append({'sourceKey': key, 'status': 'skipped_existing', 'cmsId': existing[0]['id']})
                continue
            if previous and not existing:
                raise ValueError('Previously imported CMS record is missing; do not recreate automatically')
            if not existing:
                duplicate = next((g for k, g in state['groups'].items() if k != key and set(hashes.values()).issubset(set(g.get('hashes', {}).values()))), None)
                if duplicate:
                    result.append({'sourceKey': key, 'status': 'skipped_same_media', 'cmsId': duplicate['cmsId']})
                    continue
            if existing and (existing[0].get('revision') or existing[0]['status'] != 'published'):
                raise ValueError('Existing record has an unpublished revision or status; preserve it')
            evidence = [Path(path) for path in group.get('evidence', [])]
            if not evidence or not all(path.is_file() and path.stat().st_size for path in evidence):
                raise ValueError('Saved original-post evidence is required')
            fields = cms_content.validate(group['fields'])
            if not all(fields.get(k) for k in ('title', 'description', 'category', 'tags')) or not fields.get('source', {}).get('author'):
                raise ValueError('Title, description, category, tags and verified author are required')
            fields['source']['url'] = group['sourceUrl']
            fields['type'] = 'showcase' if len(items) == 1 and items[0]['kind'] == 'video' else 'graphic'
            fields['media'] = copy_media(items, key)
            if group.get('remoteVideo') and fields['type'] == 'showcase':
                cms_content.safe_url(group['remoteVideo'])
                fields['media']['remote_video'] = group['remoteVideo']
            if existing:
                # Preserve manual moves even when a later scan adds or replaces media.
                target_type = fields['type'] if existing[0]['type'] == previous.get('autoType') else existing[0]['type']
                patch = {'type': target_type, 'media': fields['media'], '_version': existing[0]['_version']}
                current = cms_content.change(existing[0]['id'], 'edit', patch)
            else:
                current = cms_content.create(fields)
            # Record the ID before lifecycle transitions so a retry cannot duplicate it.
            state['groups'][key] = {'cmsId': current['id'], 'hashes': hashes, 'aliases': sorted(aliases),
                                    'ownership': 'eagle', 'autoType': fields['type'],
                                    'sourceUrl': group['sourceUrl'], 'checkedAt': store.now_iso()}
            save(state_path, state)
            current = cms_content.change(current['id'], 'submit', {'_version': current['_version']})
            current = cms_content.change(current['id'], 'approve', {'_version': current['_version']})
            state['groups'][key]['publishedAt'] = current['published_at']
            save(state_path, state)
            result.append({'sourceKey': key, 'status': 'updated' if existing else 'published',
                           'cmsId': current['id'], 'type': current['type'], 'title': current['title'], 'assets': len(items)})
        except Exception as error:
            result.append({'sourceKey': key, 'status': 'failed', 'error': str(error)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--apply', type=Path)
    parser.add_argument('--state', type=Path, default=ROOT/'output/eagle-intake/state.json')
    args = parser.parse_args()
    inventory = scan(args.library)
    # A partial scan must never replace the last complete source inventory.
    save(args.output/('inventory.json' if inventory['complete'] else 'inventory.partial.json'), inventory)
    if args.apply:
        result = apply_manifest(inventory, json.loads(args.apply.read_text()), args.state)
        save(args.output/'result.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(not inventory['complete'] or any(item['status'] == 'failed' for item in result))
    print(json.dumps({'items': len(inventory['items']), 'sources': len({i['sourceKey'] for i in inventory['items']}),
                      'failures': inventory['failures']}, ensure_ascii=False))
    return 0 if inventory['complete'] else 2


if __name__ == '__main__':
    sys.exit(main())
