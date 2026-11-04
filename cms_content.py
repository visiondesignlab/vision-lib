"""Validated content lifecycle and revision isolation on the shared atomic store."""
import copy
import re
import uuid
from urllib.parse import urlsplit, unquote
import store

TYPES = {'video', 'showcase', 'graphic', 'brand_skill', 'skill_repo'}
TEXT = {'title', 'subtitle', 'category', 'prompt', 'trust', 'version', 'notes', 'analysis', 'brand', 'description'}
LISTS = {'how_to', 'tags', 'tools'}
OBJECT_LISTS = {'skills', 'assets', 'changelog'}
EDITABLE = TEXT | LISTS | OBJECT_LISTS | {'type', 'featured', 'source', 'media'}
PRIVATE = {'discovery', 'revision', 'review_log', 'notes', '_version', 'origin'}


class ContentError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def public_view(c):
    return {k: v for k, v in c.items() if k not in PRIVATE}


def admin_view(c):
    result = copy.deepcopy(c)
    revision = result.pop('revision', None)
    if revision:
        result.update(revision)
    result['live_status'] = c.get('status')
    result['has_revision'] = bool(revision)
    return result


def safe_url(value, local=False):
    if not isinstance(value, str) or len(value) > 4096:
        raise ContentError('链接格式不正确')
    if not value:
        return value
    if any(ch.isspace() for ch in value) or '\\' in value:
        raise ContentError('链接中不能包含空白或反斜杠')
    parsed = urlsplit(value)
    if parsed.scheme in ('http', 'https') and parsed.netloc and not parsed.username:
        return value
    decoded = unquote(parsed.path)
    if local and re.match(r'^/(media|brand_skills|static)/', value) and '..' not in decoded.split('/') and '\\' not in decoded:
        return value
    raise ContentError('请使用完整的 http / https 链接或站内素材地址')


def validate(patch):
    if not isinstance(patch, dict):
        raise ContentError('内容需为 JSON 对象')
    unknown = set(patch) - EDITABLE - {'_version'}
    if unknown:
        raise ContentError('不支持的字段：' + ', '.join(sorted(unknown)))
    out = {}
    for k, v in patch.items():
        if k == '_version':
            continue
        if k in TEXT or k == 'type':
            if not isinstance(v, str) or len(v) > (50000 if k in {'prompt', 'description', 'analysis', 'notes'} else 500):
                raise ContentError(f'{k} 内容格式或长度不正确')
            v = v.strip()
            if k == 'type' and v not in TYPES:
                raise ContentError('请选择有效的内容类型')
        elif k == 'featured':
            if not isinstance(v, bool):
                raise ContentError('推荐字段需为布尔值')
        elif k in LISTS:
            if not isinstance(v, list) or len(v) > 100 or any(not isinstance(x, str) or len(x) > 5000 for x in v):
                raise ContentError(f'{k} 列表格式不正确')
        elif k in OBJECT_LISTS:
            if not isinstance(v, list) or len(v) > 100:
                raise ContentError(f'{k} 列表格式不正确')
            allowed = {'name', 'url', 'repo'} if k != 'changelog' else {'version', 'date', 'note'}
            for x in v:
                if not isinstance(x, dict) or set(x) - allowed or any(not isinstance(t, str) or len(t) > 5000 for t in x.values()):
                    raise ContentError(f'{k} 列表内容不正确')
                if 'url' in x:
                    safe_url(x['url'], local=True)
        elif k == 'source':
            # Only author-editable metadata is accepted; keep trusted metrics separately.
            allowed = {'platform', 'author', 'author_url', 'url', 'date'}
            if not isinstance(v, dict) or set(v) - allowed:
                raise ContentError('来源格式不正确')
            for name, value in v.items():
                if not isinstance(value, str) or len(value) > 4096:
                    raise ContentError('来源内容格式不正确')
                if name in {'url', 'author_url'}:
                    safe_url(value)
        elif k == 'media':
            if not isinstance(v, dict) or set(v) - {'kind', 'thumbnail', 'video', 'preview', 'images', 'specs', 'embed', 'remote_video'}:
                raise ContentError('媒体格式不正确')
            if v.get('kind', 'image') not in {'image', 'images', 'video'}:
                raise ContentError('媒体类型不正确')
            if 'embed' in v and v['embed'] not in ('remote', ''):
                raise ContentError('媒体嵌入格式不正确')
            for name in ('thumbnail', 'video', 'preview', 'remote_video'):
                safe_url(v.get(name, ''), local=True)
            images = v.get('images', [])
            if not isinstance(images, list) or len(images) > 30:
                raise ContentError('最多支持 30 张图片')
            for img in images:
                safe_url(img, local=True)
            specs = v.get('specs', {})
            if not isinstance(specs, dict) or any(not isinstance(t, (str, int, float)) for t in specs.values()):
                raise ContentError('媒体规格格式不正确')
        out[k] = copy.deepcopy(v)
    return out


def ready(c):
    if not c.get('title', '').strip():
        raise ContentError('请填写内容标题')
    if c.get('type') not in TYPES or not c.get('category', '').strip():
        raise ContentError('请选择内容类型并填写分类')
    m = c.get('media', {})
    if c['type'] in {'video', 'showcase'} and not (m.get('video') or c.get('source', {}).get('url')):
        raise ContentError('请上传视频或填写作品来源链接')
    if c['type'] == 'graphic' and not (m.get('thumbnail') or m.get('images')):
        raise ContentError('请上传平面图片或填写封面链接')
    if c['type'] in {'brand_skill', 'skill_repo'} and not (c.get('prompt') or c.get('assets') or c.get('source', {}).get('url')):
        raise ContentError('请填写 Prompt、添加附件或填写来源链接')


def record(c, action, note=''):
    c['_version'] = c.get('_version', 0) + 1
    c['updated_at'] = store.now_iso()
    c.setdefault('review_log', []).append({'at': c['updated_at'], 'action': action, 'note': note})


def create(patch):
    values = validate(patch)
    c = {'id': 'cms-' + uuid.uuid4().hex[:16], 'type': 'video', 'title': '', 'category': '',
         'status': 'draft', 'origin': 'cms', 'source': {}, 'media': {}, 'added_at': store.now_iso()}
    c.update(values)
    record(c, 'create')
    with store.locked():
        cases = store.load_cases()
        cases.append(c)
        store.save_cases(cases)
    return admin_view(c)


def change(cid, action, payload):
    if not isinstance(payload, dict):
        raise ContentError('内容需为 JSON 对象')
    with store.locked():
        cases = store.load_cases()
        c = next((x for x in cases if x['id'] == cid), None)
        if not c:
            raise ContentError('内容不存在', 404)
        if payload.get('_version') != c.get('_version', 0):
            raise ContentError('内容已被更新，请刷新后再操作', 409)
        current = admin_view(c)
        note = payload.get('note', '')
        if not isinstance(note, str) or len(note) > 2000:
            raise ContentError('审核意见最多 2000 字')
        if action == 'edit':
            patch = validate(payload)
            # Preserve source metrics maintained by background collection.
            if 'source' in patch:
                patch['source'] = {**current.get('source', {}), **patch['source']}
            if c['status'] == 'published':
                revision = copy.deepcopy(c.get('revision') or {k: v for k, v in c.items() if k in EDITABLE})
                revision.update(patch)
                revision['status'] = 'draft'
                c['revision'] = revision
            else:
                c.update(patch)
                c['status'] = 'draft'
        elif action == 'submit':
            if current['status'] not in {'draft', 'rejected', 'archived'}:
                raise ContentError('当前内容不需要重复提交', 409)
            ready(current)
            target = c.get('revision', c)
            target['status'] = 'pending'
        elif action == 'approve':
            if current['status'] != 'pending':
                raise ContentError('只有待审核内容可以发布', 409)
            ready(current)
            revision = c.pop('revision', None)
            if revision:
                c.update(revision)
            c['status'] = 'published'
            c['published_at'] = store.now_iso()
        elif action == 'reject':
            if current['status'] != 'pending':
                raise ContentError('只有待审核内容可以退回', 409)
            if not note.strip():
                raise ContentError('请填写退回原因')
            c.get('revision', c)['status'] = 'rejected'
            if not c.get('revision') and c.get('origin') != 'cms':
                rejected = store.load_rejected()
                rejected.extend(store.norm_url(u) for u in (c.get('source', {}).get('url'), c.get('source', {}).get('via_url')) if u)
                store.save_rejected(rejected)
        elif action == 'unpublish':
            if c['status'] != 'published':
                raise ContentError('内容尚未发布', 409)
            revision = c.pop('revision', None)
            if revision:
                c.update(revision)
            c['status'] = 'archived'
        else:
            raise ContentError('不支持的操作')
        record(c, action, note.strip())
        store.save_cases(cases)
        return admin_view(c)


def references(value, path):
    if isinstance(value, str):
        return value.split('?', 1)[0] == path
    if isinstance(value, dict):
        return any(references(v, path) for v in value.values())
    if isinstance(value, list):
        return any(references(v, path) for v in value)
    return False


def public_asset(path):
    return any(c.get('status') == 'published' and references(public_view(c), path) for c in store.load_cases())
