"""Private submission inbox. Public catalogs only contain explicitly published cases."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import cms_content as cms
from mediautil import https_context
from cms_migration import video_identity
from submission_media import analyze_media, classify, public_link, resolve_media
import store

WAKE = threading.Event()
SYNC = threading.Lock()
KINDS = {'video':'AI 视频案例', 'showcase':'灵感库'}


def path():
    return os.path.join(store.DATA, 'submissions.json')


def read():
    return store._read(path(), {'items':{}, 'cursor':0})


def validate(body):
    rid = body.get('id')
    if not isinstance(rid, str) or not re.fullmatch(r'[0-9a-f]{32}', rid):
        raise cms.ContentError('投稿编号无效')
    try:
        url = public_link(body.get('url'))
    except ValueError as exc:
        raise cms.ContentError('请填写完整的公开作品链接') from exc
    fields = {}
    for name, limit in [('title',160),('note',1600)]:
        value = body.get(name, '')
        if not isinstance(value,str) or len(value)>limit:
            raise cms.ContentError('标题或说明太长')
        fields[name] = value.strip()
    return dict(id=rid, url=url, **fields)


def insert(db, body, origin):
    item = validate(body)
    db['items'].setdefault(item['id'], dict(**item, origin=origin, created=store.now_iso(), status='queued', version=1))
    return item['id']


def receive(body):
    with store.locked():
        db = read()
        rid = insert(db, body, 'local')
        store._write(path(), db)
    WAKE.set()
    return {'receipt':rid}


def listing():
    with store.locked():
        db, cases = read(), {c['id']:c for c in store.load_cases()}
    items = sorted(db['items'].values(), key=lambda i: i['created'], reverse=True)
    return {'items':[dict(i, case_status=cases.get(i.get('case_id'), {}).get('status')) for i in items],
            'connected':bool(remote_config()[0] and remote_config()[1])}


def remote_config():
    conf = store._read(os.path.join(store.DATA,'submission-relay.json'), {})
    return (os.getenv('VISION_INTAKE_URL') or conf.get('url',''), os.getenv('VISION_INTAKE_READ_TOKEN') or conf.get('token',''))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def sync():
    url, token = remote_config()
    u = urlsplit(url)
    if not token or not u.netloc or u.username or u.password or (u.scheme!='https' and not
            (u.scheme=='http' and u.hostname in ('127.0.0.1','localhost','::1'))):
        raise cms.ContentError('请先配置私密收件服务及本地读取密钥', 503)
    count = 0
    with SYNC:
        for _ in range(20):
            with store.locked():
                cursor = read()['cursor']
            req = Request(url.rstrip('/')+'/sync?after='+str(cursor),headers={'Authorization':'Bearer '+token,'User-Agent':'VisionLab-CMS/1.0','Accept':'application/json'})
            try:
                with build_opener(NoRedirect(),HTTPSHandler(context=https_context())).open(req,timeout=12) as response:
                    batch = json.load(response)['items']
                if not isinstance(batch,list) or len(batch)>100:
                    raise ValueError()
                with store.locked():
                    db = read()
                    for row in batch:
                        if not isinstance(row['seq'],int) or row['seq']<=db['cursor']:
                            raise ValueError()
                        rid=insert(db,row,'pages')
                        db['items'][rid]['created']=row['created']
                        db['cursor']=row['seq']
                    store._write(path(),db)
            except (ValueError,OSError,KeyError,cms.ContentError) as exc:
                raise cms.ContentError('同步失败，请检查收件地址、密钥和网络后重试',502) from exc
            count += len(batch)
            if len(batch)<100:
                break
    WAKE.set()
    return {'received':count}


def review(rid, body):
    with store.locked():
        db=read()
        item=db['items'].get(rid)
        if not item:
            raise cms.ContentError('投稿不存在',404)
        if item['status'] in ('linked','duplicate') or item['version']!=body.get('version'):
            raise cms.ContentError('投稿状态已变化，请刷新后重试',409)
        action=body.get('action')
        if action=='archive':
            item['status']='archived'
        elif action=='process':
            target=body.get('target','')
            attachment=body.get('attachment','')
            if target not in ('',*KINDS):
                raise cms.ContentError('请选择有效栏目')
            if attachment:
                if not isinstance(attachment,str) or not re.fullmatch(r'/media/cms-assets-[0-9a-f]{32}/web\.mp4',attachment):
                    raise cms.ContentError('请通过上传控件提供视频')
                if not (Path(store.MEDIA) / attachment.removeprefix('/media/')).is_file():
                    raise cms.ContentError('上传的视频不存在')
                item['attachment']=attachment
                item.pop('analysis',None)
                item.pop('media',None)
            item.update(status='queued', override=target)
        else:
            raise cms.ContentError('无效操作')
        item['version']+=1
        store._write(path(),db)
    WAKE.set()
    return {'ok':True}


def duplicate(item, cases):
    identity = video_identity(item['url'])
    return next((c for c in cases if video_identity((c.get('source') or {}).get('url'))==identity),None)


def finish(item, updated):
    with store.locked():
        db=read()
        row=db['items'].get(item['id'])
        if not row or row['version']!=item['version'] or row['status']!='queued':
            return
        cases=store.load_cases()
        peer=duplicate(row,cases)
        row.update(updated)
        cid='sub-'+row['id']
        if peer:
            row.update(status='linked' if peer['id']==cid else 'duplicate',case_id=peer['id'])
        elif row.get('target') in KINDS and row.get('analysis') and row.get('media'):
            title=row.get('title') or row.get('source_title') or urlsplit(row['url']).hostname+' 视频'
            report=row['analysis']
            c=dict(id=cid, origin='submission', status='pending', type=row['target'], title=title, category='待分类',
                   source={'url':row['url']}, media=row['media'], tags=[], added_at=store.now_iso())
            if c['type']=='video':
                c['shot_analysis']=report
                c['how_to']=report['steps']
                c['subtitle']=f'{report["duration"]:g} 秒 · {len(report["shots"])} 个镜头'
                c['prompt']=f'参考《{title}》的分镜和时长，生成同结构的短片。'+' '.join(report['steps'])
            cms.record(c,'submit','由私密投稿导入')
            cases.append(c)
            store.save_cases(cases)
            row.update(status='linked',case_id=cid)
        row['version']+=1
        store._write(path(),db)


def process(item):
    with store.locked():
        peer = duplicate(item,store.load_cases())
    if peer:
        return finish(item,{})
    media, report = item.get('media'), item.get('analysis')
    title=item.get('source_title','')
    description=item.get('source_description','')
    opinion=item.get('opinion',{})
    problem=''
    if not report:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                file, title, description=resolve_media(item,Path(tmp))
                if file:
                    # Different attachments receive independent, atomic renditions.
                    key = item['attachment'].split('/')[2] if item.get('attachment') else 'source'
                    media,report,opinion=analyze_media(file,'intake-'+item['id']+'-'+key)
        except (OSError,RuntimeError,ValueError,ImportError,subprocess.SubprocessError):
            problem='未能读取或分析完整视频，可补传原片后重试'
    target,reason=classify(item['title']+' '+title,item['note'],description)
    if not target and opinion.get('type') in KINDS and opinion.get('confidence')=='high' and opinion.get('evidence'):
        target,reason=opinion['type'],'关键帧判断：'+str(opinion['evidence'])[:500]
    if item.get('override'):
        target,reason=item['override'],'管理员已核对制作方式'
    finish(item,dict(status='review' if report else 'needs_video',reason=reason,target=target,source_title=title,
                     source_description=description,media=media,analysis=report,opinion=opinion,
                     problem=problem or ('' if report else '链接未提供可读取的视频，请补传原片')))


def start():
    def jobs():
        while True:
            WAKE.clear()
            with store.locked():
                item=next((i for i in read()['items'].values() if i['status']=='queued'),None)
            if not item:
                WAKE.wait(20)
                continue
            try:
                process(item)
            except Exception:
                finish(item,dict(status='review',problem='本地处理失败，请检查来源或补传视频后重试'))
    def polling():
        while True:
            try:
                if all(remote_config()):
                    sync()
            except (OSError,ValueError,cms.ContentError):
                pass
            time.sleep(60)
    threading.Thread(target=jobs, daemon=True,name='submission-review').start()
    threading.Thread(target=polling, daemon=True,name='submission-sync').start()
