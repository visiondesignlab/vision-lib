"""Compare video records and move existing records between the two video sections."""
import re
from collections import defaultdict
from urllib.parse import parse_qsl, urlencode, urlsplit

from cms_content import ContentError, admin_view, record
import store

SECTIONS = {'video': '视频案例', 'showcase': '灵感库'}


def video_identity(url):
    """Preserve resource-defining queries such as YouTube's v parameter."""
    if not url:
        return ''
    parts = urlsplit(url)
    host = (parts.hostname or '').lower().removeprefix('www.')
    path = parts.path.rstrip('/')
    if host in ('x.com', 'twitter.com', 'mobile.twitter.com', 'mobile.x.com'):
        match = re.search(r'/status(?:es)?/(\d+)', path)
        if match:
            return 'x.com/status/' + match[1]
    if host == 'video.twimg.com':
        match = re.match(r'/(ext_tw_video|amplify_video)/(\d+)/', path)
        if match:
            return host + '/' + '/'.join(match.groups())
    if not path and not parts.query:
        return ''
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
    return host + path + ('?' + urlencode(sorted(query)) if query else '')


def matching_records(cases):
    index = defaultdict(set)
    views = {c['id']: admin_view(c) for c in cases}
    for c in cases:
        for view in (c, views[c['id']]):
            if view['type'] not in SECTIONS:
                continue
            source, media = view.get('source') or {}, view.get('media') or {}
            for reason, key in [('同一原帖', video_identity(source.get('url'))),
                                ('同一视频', video_identity(media.get('video'))),
                                ('同一视频', video_identity(media.get('remote_video'))),
                                ('标题相同', ' '.join((view.get('title') or '').casefold().split()))]:
                if key:
                    index[reason, key].add(c['id'])
    result = defaultdict(dict)
    for (reason, _), ids in index.items():
        for cid in ids:
            for peer in ids - {cid}:
                result[cid].setdefault(peer, set()).add(reason)
    return {cid: [{'id': pid, 'title': views[pid].get('title') or pid, 'type': views[pid]['type'],
                   'reasons': sorted(reasons)} for pid, reasons in sorted(peers.items())]
            for cid, peers in result.items()}


def transfer(payload):
    items, target = payload.get('items'), payload.get('target')
    if not isinstance(target, str) or target not in SECTIONS or not isinstance(items, list) or not items:
        raise ContentError('请选择视频内容和目标栏目')
    applying = payload.get('apply') is True
    with store.locked():
        cases = store.load_cases()
        by_id = {c['id']: c for c in cases}
        selected = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                raise ContentError('无效的迁移条目')
            cid = item['id']
            c = by_id.get(cid)
            if not c or item.get('_version') != c.get('_version', 0):
                raise ContentError('内容已更新，请刷新列表后重试。', 409)
            if cid in selected or c.get('type') not in SECTIONS or c['type'] == target or admin_view(c)['type'] != c['type']:
                raise ContentError('请选择另一视频栏目的内容；有待审栏目变更时，请先完成审核。', 409)
            selected[cid] = c
        matches = matching_records(cases)
        conflicts = {cid: [p for p in matches.get(cid, []) if p['id'] in selected or
                           target in (p['type'], by_id[p['id']]['type'])] for cid in selected}
        conflicts = {cid: peers for cid, peers in conflicts.items() if peers}
        if not applying:
            return {'conflicts': conflicts}
        if payload.get('confirmed', {}) != conflicts:
            raise ContentError('重复情况发生变化，请关闭窗口并重新核对。', 409)
        category = payload.get('category', '')
        if not isinstance(category, str) or not category.strip() or len(category) > 500:
            raise ContentError('请填写目标栏目中的分类')
        for c in selected.values():
            before = c['type']
            c.update(type=target, category=category.strip())
            if c.get('revision'):
                c['revision'].update(type=target, category=category.strip())
            record(c, 'migrate', f'{SECTIONS[before]} → {SECTIONS[target]} · {c["category"]}')
        store.save_cases(cases)
        return {'moved': len(selected)}
