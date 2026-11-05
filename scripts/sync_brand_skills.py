#!/usr/bin/env python3
"""Sync curated public GitHub skills into the local case library, pinned per import."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import store


def github(endpoint):
    return subprocess.check_output(['gh', 'api', endpoint], cwd=ROOT)


def write_asset(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(content)
    os.replace(tmp.name, path)


def fetch_skill(spec):
    repository = spec['repo']
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repository):
        raise ValueError(f'Invalid repository: {repository}')
    meta = json.loads(github(f'repos/{repository}'))
    if meta['visibility'] != 'public':
        raise ValueError(f'Repository must be public: {repository}')
    branch = meta['default_branch']
    head = json.loads(github(f'repos/{repository}/commits/{branch}'))
    sha, date = head['sha'], head['commit']['committer']['date'][:10]
    url = meta['html_url']
    slug = meta['name']
    cid = 'brand-' + slug
    folder = Path(store.MEDIA) / cid / sha
    prefix = f'/media/{cid}/{sha}/'
    samples = []
    archive = github(f'repos/{repository}/zipball/{sha}')
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        files = {}
        for member in source.infolist():
            path = PurePosixPath(member.filename)
            if member.is_dir():
                continue
            if path.is_absolute() or '..' in path.parts or len(path.parts) < 2:
                raise ValueError(f'Unexpected archive path: {path}')
            files['/'.join(path.parts[1:])] = member
        for required in ['SKILL.md', 'README.md', 'LICENSE', *(p for _, p in spec['docs']), *(p for _, p in spec['examples'])]:
            if required not in files:
                raise ValueError(f'{repository}@{sha[:7]} is missing {required}; review its catalog entry.')
        # Use the skill name as the archive root so the extracted folder is ready to install.
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as out:
            for relative, member in sorted(files.items()):
                item = zipfile.ZipInfo(f'{slug}/{relative}', member.date_time)
                item.external_attr = member.external_attr
                out.writestr(item, source.read(member), compress_type=zipfile.ZIP_DEFLATED)
        write_asset(folder / f'{slug}.zip', bundle.getvalue())
        for index, (label, relative) in enumerate(spec['examples'], 1):
            filename = f'sample-{index}{PurePosixPath(relative).suffix}'
            write_asset(folder / filename, source.read(files[relative]))
            samples.append({'label': label, 'url': prefix + filename})
    for label, public_path in spec.get('local_examples', []):
        path = (ROOT / public_path.lstrip('/')).resolve()
        if not path.is_relative_to(ROOT / 'static/assets/brand-skill-examples') or not path.is_file():
            raise ValueError(f'Missing curated example: {public_path}')
        samples.append({'label': label, 'url': public_path})
    if not samples:
        raise ValueError(f'{repository} needs a published example.')
    return {
        'id': cid, 'type': 'brand_skill', 'brand': 'viaim', 'trust': '官方',
        **{key: spec[key] for key in ('title','category','subtitle','description','prompt','how_to','tags')},
        'version': sha[:7], 'media': {'kind':'image', 'thumbnail': samples[0]['url'], 'images':[s['url'] for s in samples]},
        'source': {'platform':'GitHub', 'author':meta['owner']['login'], 'repo':repository, 'url':url, 'date':date,
                   'metrics':{'stars':meta['stargazers_count']}},
        'assets':[{'name':'Skill 安装包', 'url':prefix + f'{slug}.zip'}],
        'brand_repository': {'sha':sha, 'branch':branch, 'license':(meta['license'] or {}).get('spdx_id') or '未标注',
                             'installation':spec['installation'], 'install_command':spec.get('install_command',''), 'samples':samples,
                             'cover_count':spec.get('cover_count', 1), 'sample_source':spec.get('sample_source',''),
                             'docs':[{'name':label,'url':f'{url}/blob/{sha}/{path}'} for label,path in [('Skill 文档','SKILL.md'), *spec['docs']]]},
    }


def main():
    specs = json.loads((ROOT / 'catalog/brand-skill-sources.json').read_text())
    names = [spec['repo'].split('/')[-1].casefold() for spec in specs]
    if len(names) != len(set(names)):
        raise ValueError('Each catalog entry needs a distinct skill directory name.')
    with store.locked():
        initial = {c['id']: c for c in store.load_cases()}
    records = [fetch_skill(spec) for spec in specs]
    changed = 0
    with store.locked():
        cases = store.load_cases()
        existing = {c['id']: c for c in cases}
        removed = set(store.load_rejected())
        for data in records:
            cid = data['id']
            current = existing.get(cid)
            if current is None and store.norm_url(data['source']['url']) in removed:
                raise ValueError(f'{cid} was removed from the library; review its catalog entry.')
            if current != initial.get(cid) or current and (current.get('revision') or not current.get('brand_repository')):
                raise ValueError(f'{cid} has a pending or conflicting edit; import stopped.')
            if current and all(current.get(key) == value for key, value in data.items()):
                continue
            if current is None:
                current = {'status':'published', 'added_at':store.now_iso(), 'origin':'brand-skill-sync', 'changelog':[]}
                cases.append(current)
            if current.get('version') != data['version']:
                current.setdefault('changelog', []).append({'version':data['version'], 'date':data['source']['date'], 'note':'同步 GitHub 仓库版本。'})
            current.update(data, updated_at=store.now_iso(), _version=current.get('_version', 0) + 1)
            changed += 1
        if changed:
            store.save_cases(cases)
    for data in records:
        print(f"{data['source']['repo']} @ {data['version']}")
    print(f'{changed} record(s) updated.')


if __name__ == '__main__':
    main()
