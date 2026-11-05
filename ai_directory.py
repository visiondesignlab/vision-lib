"""AI directory: a curated seed with an atomic, administrator-editable local copy."""
import json
import re
from pathlib import Path
import uuid

from cms_content import ContentError, safe_url
import store


def spaced(text):
    return re.sub(r'(?<=[㐀-鿿])[ \t]*(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])[ \t]*(?=[㐀-鿿])', ' ', text)


def load():
    path = Path(store.DATA) / 'ai-directory.json'
    if not path.exists():
        path = Path(store.ROOT) / 'publish/ai-directory.json'
        if not path.exists():
            path = Path(store.ROOT) / 'catalog/ai-directory.json'
    db = json.loads(path.read_text(encoding='utf-8'))
    # Public exports omit private edit metadata; start optimistic locking at zero.
    db.setdefault('version', 0)
    for row in (*db['categories'], *db['entries']):
        row['name'] = spaced(row['name'])
        if 'description' in row:
            row['description'] = spaced(row['description'])
    return db


def public_view(db):
    return {'categories': db['categories'], 'entries': db['entries']}


def string(data, key, maximum, required=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ContentError('请填写有效的' + {'name': '名称', 'description': '简介', 'url': '网址', 'category': '分类', 'icon': '图标地址'}[key])
    return value.strip()


def change(data):
    with store.locked():
        db = load()
        if type(data.get('version')) is not int or data['version'] != db.get('version', 0):
            raise ContentError('目录已在其他窗口更新，请刷新后重试。', 409)
        kind, action = data.get('kind'), data.get('action')
        if kind not in ('category', 'entry') or action not in ('save', 'delete', 'feature'):
            raise ContentError('未知的目录操作')
        groups, entries = db['categories'], db['entries']
        rows = groups if kind == 'category' else entries
        item_id = data.get('id')
        item = next((x for x in rows if x['id'] == item_id), None)
        if (item_id or action in ('delete', 'feature')) and not item:
            raise ContentError('条目不存在', 404)
        if action == 'feature':
            if kind != 'entry' or type(data.get('featured')) is not bool:
                raise ContentError('请选择有效的入口和推荐状态')
            item['featured'] = data['featured']
        elif action == 'delete':
            if kind == 'category' and any(x['category'] == item_id for x in entries):
                raise ContentError('请先移动或删除分类中的入口，再删除分类。', 409)
            rows.remove(item)
        else:
            name = spaced(string(data, 'name', 160, True))
            new_item = not item
            if new_item:
                item = {'id': uuid.uuid4().hex}
            if kind == 'category':
                if any(x is not item and x['name'].casefold() == name.casefold() for x in groups):
                    raise ContentError('已有同名分类')
                item['name'] = name
            else:
                category = string(data, 'category', 100, True)
                if not any(x['id'] == category for x in groups):
                    raise ContentError('请选择有效分类')
                url = safe_url(string(data, 'url', 4096, True))
                if any(x is not item and x['category'] == category and x['url'] == url for x in entries):
                    raise ContentError('此分类中已有相同网址')
                icon = string(data, 'icon', 4096)
                if icon != item.get('icon', ''):
                    safe_url(icon)
                item.update(name=name, category=category, url=url, icon=icon,
                            description=spaced(string(data, 'description', 500)))
            if new_item:
                rows.append(item)
        db['version'] = data['version'] + 1
        store._write(str(Path(store.DATA) / 'ai-directory.json'), db)
        return db
