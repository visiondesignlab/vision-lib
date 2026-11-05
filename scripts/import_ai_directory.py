"""Build the initial directory from the 18 AI navigation sections. Never writes to live CMS data.
One-off import dependency: beautifulsoup4. Usage: python3 scripts/import_ai_directory.py saved-page.html
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import subprocess
import sys

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai_directory import spaced

SOURCE = 'https://hao.uisdc.com/ai/'
SECTIONS = 'aiagent skills smart smart2 smart4 smart9 smart7 smart8 smart6 smart10 smart5 study gadget translate program institution smart12 aitools'.split()


def cache_icon(url):
    filename = sha256(url.encode()).hexdigest()[:20] + '.webp'
    folder = ROOT / 'static/tools/ai-icons'
    folder.mkdir(exist_ok=True)
    target = folder / filename
    if not target.exists():
        try:
            if urlsplit(url).hostname != 'image.uisdc.com':
                return ''
            raw = subprocess.run(['curl', '-fsSL', '--max-time', '15', '--max-filesize', '4000000',
                                  '--referer', SOURCE, '--', url], check=True, capture_output=True).stdout
            icon = Image.open(BytesIO(raw)).convert('RGBA')
            icon.thumbnail((96, 96))
            icon.save(target, 'WEBP', quality=90)
        except (OSError, ValueError, subprocess.CalledProcessError):
            return ''
    return '/static/tools/ai-icons/' + filename


def extract(html):
    soup = BeautifulSoup(html, 'html.parser')
    blocks = {b.select_one('h2')['id']: b for b in soup.select('.part-cat-block') if b.select_one('h2[id]')}
    groups, entries, icons = [], [], {}
    for key in SECTIONS:
        block = blocks[key]
        groups.append({'id': key, 'name': spaced(block.select_one('h2 strong').get_text(strip=True))})
        seen = set()
        for a in block.select('.p-item a.f-box'):
            url = urljoin(SOURCE, a['href'].strip())
            if urlsplit(url).scheme not in ('http', 'https') or not urlsplit(url).hostname:
                raise ValueError('Unsupported destination: ' + url)
            if url in seen:
                continue
            seen.add(url)
            title = spaced(a.select_one('.title').get_text(strip=True))
            entry = {'id': sha256((key + '\n' + url).encode()).hexdigest()[:20], 'category': key,
                     'name': title, 'url': url, 'description': ''}
            entries.append(entry)
            img = a.select_one('img[src]')
            if img:
                icons[entry['id']] = urljoin(SOURCE, img['src'])
        if not seen:
            raise ValueError('Empty source section: ' + key)
    urls = sorted(set(icons.values()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        cached = dict(zip(urls, pool.map(cache_icon, urls)))
    for item in entries:
        item['icon'] = cached.get(icons.get(item['id']), '')
    return {'categories': groups, 'entries': entries}


def apply_curation(db, original_ids=()):
    """Merge verified product listings by stable ID. Never revive a locally removed seed."""
    updates = json.loads((ROOT / 'catalog/ai-directory-curation.json').read_text())['entries']
    by_id = {e['id']: e for e in db['entries']}
    for patch in updates:
        row = by_id.get(patch['id'])
        if row is None and patch['id'] not in original_ids and 'url' in patch:
            row = by_id[patch['id']] = {}
        if row is not None:
            row.update(patch)
        for retired in patch.get('previousIds', ()):
            removed = by_id.pop(retired, {})
            if row is not None and removed.get('featured'):
                row['featured'] = True
    # Keep curated tools together at the start of their category.
    picks = [by_id[p['id']] for p in updates if 'category' in p and p['id'] in by_id]
    picked = {p['id'] for p in picks}
    db['entries'] = picks + [e for e in by_id.values() if e['id'] not in picked]


def build_atlas(db):
    # One retina-resolution sprite avoids hundreds of simultaneous image requests.
    icons = sorted({e['icon'] for e in db['entries'] if e['icon']})
    if not icons:
        raise ValueError('No product icons were downloaded; keeping the previous catalog.')
    size, columns = 64, 16
    rows = (len(icons) + columns - 1) // columns
    atlas = Image.new('RGBA', (columns * size, rows * size))
    css = [f'.ai-icon[data-asset]{{background-image:url("ai-icons/atlas.webp");background-repeat:no-repeat;background-size:{columns * 32}px {rows * 32}px}}']
    for index, icon in enumerate(icons):
        tile = Image.open(ROOT / icon.lstrip('/')).convert('RGBA')
        tile.thumbnail((size, size))
        x, y = (index % columns), (index // columns)
        atlas.paste(tile, (x * size + (size-tile.width)//2, y * size + (size-tile.height)//2))
        key = Path(icon).stem
        css.append(f'.ai-icon[data-asset="{key}"]{{background-position:{-x*32}px {-y*32}px}}')
    folder = ROOT / 'static/tools'
    atlas.save(folder / 'ai-icons/atlas.webp', 'WEBP', lossless=True)
    (folder / 'ai-icon-atlas.css').write_text('\n'.join(css)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    args = parser.parse_args()
    db = extract(args.html.read_text())
    dest = ROOT / 'catalog/ai-directory.json'
    # Keep locally authored descriptions on refresh; live edits live in the separate CMS store.
    previous = {x['id']: x['description'] for x in json.loads(dest.read_text())['entries']} if dest.exists() else {}
    for x in db['entries']:
        x['description'] = previous.get(x['id'], '')
    apply_curation(db)
    build_atlas(db)
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(db, ensure_ascii=False, indent=1) + '\n')
    print(f"{len(db['categories'])} groups, {len(db['entries'])} entries, {sum(bool(x['icon']) for x in db['entries'])} icons")
