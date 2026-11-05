#!/usr/bin/env python3
"""Build a backend-free Pages site, preserving project paths and deep links."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = {'discovery', 'revision', 'review_log', 'notes', '_version', 'origin'}


def prefix(value, base):
    if isinstance(value, dict):
        return {k: prefix(v, base) for k, v in value.items()}
    if isinstance(value, list):
        return [prefix(v, base) for v in value]
    if isinstance(value, str) and value.startswith(('/media/', '/static/', '/brand_skills/')):
        return base + value
    return value


def rebase_text(text, base):
    # Only root-relative HTML attributes and CSS URLs, not external URLs or JS.
    text = re.sub(r'((?:href|src)=[\"\'])(/(?!/))', lambda m: m[1] + base + m[2], text)
    return re.sub(r'(url\([\"\']?)(/(?!/))', lambda m: m[1] + base + m[2], text)


def check_media(value, output):
    if isinstance(value, dict):
        for child in value.values():
            check_media(child, output)
    elif isinstance(value, list):
        for child in value:
            check_media(child, output)
    elif isinstance(value, str) and value.startswith(('/media/', '/brand_skills/')):
        target = (output / value.lstrip('/')).resolve()
        if not target.is_relative_to(output) or not target.is_file():
            raise ValueError(f'Missing published asset: {value}')


def build(output, base):
    base = '/' + base.strip('/') if base.strip('/') else ''
    if not re.fullmatch(r'(?:/[A-Za-z0-9._-]+)*', base):
        raise ValueError('Invalid project base path')
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output in (ROOT / 'static', ROOT / 'publish'):
        raise ValueError('Unsafe output directory')
    if output.exists():
        if not (output / '.vision-pages-build').exists():
            raise ValueError('Output exists and is not an owned Pages build directory')
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / '.vision-pages-build').touch()
    snapshot = json.loads((ROOT / 'publish/cases.json').read_text())
    cases = snapshot['cases']
    ids = set()
    for case in cases:
        if case.get('status') != 'published' or PRIVATE.intersection(case):
            raise ValueError('Snapshot contains non-public content')
        cid = case['id']
        if not re.fullmatch(r'[\w.-]+', cid) or cid in ids:
            raise ValueError('Invalid or duplicate case ID')
        ids.add(cid)
    # Never copy the private store, logs, backups, CMS code or arbitrary media.
    excluded = {'README.md', 'cms.js', 'cms-select.js', 'cms-directory.js', 'cms.html', '.DS_Store'}
    shutil.copytree(ROOT / 'static', output / 'static', ignore=lambda d, names: set(names) & excluded)
    for directory in ('media', 'brand_skills'):
        if (ROOT / 'publish' / directory).exists():
            shutil.copytree(ROOT / 'publish' / directory, output / directory)
    check_media(cases, output)
    for asset in json.loads((ROOT / 'publish/large-assets.json').read_text()):
        target = output / asset['path']
        if not target.resolve().is_relative_to(output):
            raise ValueError('Invalid release asset path')
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            print(f"Downloading {asset['name']}", flush=True)
            with urllib.request.urlopen(asset['url'], timeout=120) as response, target.open('wb') as dest:
                shutil.copyfileobj(response, dest)
        if target.stat().st_size != asset['bytes'] or hashlib.sha256(target.read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError(f"Release asset integrity check failed: {asset['name']}")
    manifest = output / 'static/assets/viaim/manifest.json'
    manifest.write_text(json.dumps(prefix(json.loads(manifest.read_text()), base), ensure_ascii=False, indent=2))
    for target in (output / 'static').rglob('*'):
        if target.suffix in ('.css', '.html'):
            target.write_text(rebase_text(target.read_text(), base))
    shell = (output / 'static/index.html').read_text()
    config = json.dumps({'staticMode': True, 'basePath': base}, ensure_ascii=False)
    shell = shell.replace('<script src=', '<script>window.VISION_CONFIG = ' + config + ';</script>\n<script src=', 1)
    (output / 'index.html').write_text(shell)
    (output / '404.html').write_text(shell)
    (output / 'static/index.html').unlink()
    for route in ['tools/ai-nav', 'tools/image-slicer', 'assets/brand', 'assets/design', 'review', 'cms', 'guide', *('c/' + cid for cid in sorted(ids))]:
        target = output / route / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(shell)
    public = output / 'public'
    public.mkdir()
    (public / 'cases.json').write_text(json.dumps(prefix(snapshot, base), ensure_ascii=False, separators=(',', ':')))
    catalog = ROOT / 'publish/ai-directory.json'
    if not catalog.exists():
        catalog = ROOT / 'catalog/ai-directory.json'
    db = json.loads(catalog.read_text())
    (public / 'ai-directory.json').write_text(json.dumps({key: db[key] for key in ('categories', 'entries')}, ensure_ascii=False))
    guide = (ROOT / 'docs/pages-guide.md').read_text()
    (output / 'static/README.md').write_text(guide)
    # Legacy bookmarks use the same shell; the router canonicalizes to /guide.
    manual = output / 'static/README.html'
    manual.write_text(shell)
    (output / '.nojekyll').touch()
    total = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    if total >= 1024 ** 3:
        raise ValueError(f'Pages output exceeds 1 GiB: {total} bytes')
    report = {'cases': len(cases), 'basePath': base, 'bytes': total, 'routes': len(ids) + 7}
    (output / 'build-info.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--base-path', default='/vision-lib')
    args = parser.parse_args()
    build(args.output, args.base_path)
