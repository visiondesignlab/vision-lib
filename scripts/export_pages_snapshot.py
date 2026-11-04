#!/usr/bin/env python3
"""Export only approved public data and its referenced media for version control."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cms_content
import store


def references(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)
    elif isinstance(value, str) and value.startswith(('/media/', '/brand_skills/')):
        yield unquote(urlsplit(value).path).lstrip('/')


def main():
    cases = [cms_content.public_view(c) for c in store.load_cases() if c.get('status') == 'published']
    if not cases:
        raise SystemExit('No published content; refusing to replace the public snapshot.')
    output = ROOT / 'publish'
    staging = ROOT / 'output/pages-snapshot'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    assets = sorted(set(references(cases)))
    for relative in assets:
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ValueError(f'Invalid public asset: {relative}')
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (staging / 'cases.json').write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=1) + '\n')
    large = []
    for source in sorted((ROOT / 'static').rglob('*')):
        if not source.is_file() or source.stat().st_size < 80_000_000:
            continue
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        large.append({'path': str(source.relative_to(ROOT)), 'name': source.name,
                      'bytes': source.stat().st_size, 'sha256': digest,
                      'url': f'https://github.com/visiondesignlab/vision-lib/releases/download/brand-assets-2026-11-04/{source.name}'})
    (staging / 'large-assets.json').write_text(json.dumps(large, ensure_ascii=False, indent=2) + '\n')
    if output.exists():
        shutil.rmtree(output)
    shutil.move(staging, output)
    print(f'Exported {len(cases)} published records, {len(assets)} referenced assets, {len(large)} release assets.')


if __name__ == '__main__':
    main()
