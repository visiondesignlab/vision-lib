"""CMS HTTP integration checks, using only temporary data and media."""
import io
import json
import os
import sys
import subprocess
import tempfile
import threading
import unittest
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import cms_auth
import cms_content
import mediautil
import store

PASSWORD = 'cms-test-password-12345'


class Quiet(server.H):
    def log_message(self, *args):
        pass


class CMSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = self.temp.name
        self.media = os.path.join(root, 'media')
        os.makedirs(self.media)
        self.patches = [patch.object(store, k, v) for k, v in {
            'DATA': root, 'CASES': os.path.join(root, 'cases.json'), 'REJECTED': os.path.join(root, 'rejected.json'),
            'LOCK': os.path.join(root, '.lock'), 'TOKEN_FILE': os.path.join(root, 'token.txt'), 'MEDIA': self.media}.items()]
        self.patches += [patch.object(mediautil, 'MEDIA', self.media), patch.dict(server.SERVE_DIRS, {'media': self.media})]
        for p in self.patches:
            p.start()
        cms_auth._sessions.clear()
        cms_auth._attempts.clear()
        cms_auth.set_password(PASSWORD)
        store.save_cases([])
        self.server = server.ThreadingHTTPServer(('127.0.0.1', 0), Quiet)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.admin = build_opener(HTTPCookieProcessor(CookieJar()))
        self.public = build_opener()
        self.csrf = ''

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def req(self, path, data=None, method=None, auth=True, headers=None, raw=None):
        hdr = {'Content-Type': 'application/json'}
        if self.csrf and auth:
            hdr['X-CSRF-Token'] = self.csrf
        hdr.update(headers or {})
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        request = Request(self.base+path, data=body, method=method, headers=hdr)
        try:
            response = (self.admin if auth else self.public).open(request)
        except HTTPError as error:
            response = error
        payload = response.read()
        result = json.loads(payload) if response.headers.get('Content-Type','').startswith('application/json') else payload
        return response.code, result, response.headers

    def login(self):
        code, data, hdr = self.req('/api/auth/login', {'password': PASSWORD})
        self.assertEqual(code, 200)
        self.csrf = data['csrf']
        self.assertIn('HttpOnly', hdr['Set-Cookie'])
        self.assertIn('SameSite=Strict', hdr['Set-Cookie'])

    def create(self, **fields):
        code, c, _ = self.req('/api/admin/cases', {'type':'brand_skill','title':'First version','category':'规范','prompt':'A reusable prompt', **fields})
        self.assertEqual(code, 201, c)
        return c

    def action(self, c, name, **kwargs):
        code, result, _ = self.req('/api/admin/cases/'+c['id']+'/'+name, {'_version':c['_version'],**kwargs})
        self.assertEqual(code, 200, result)
        return result

    def test_public_and_cms_routes_share_the_same_shell(self):
        code, shell, _ = self.req('/?tab=video', auth=False)
        self.assertEqual(code, 200)
        for path in ('/review', '/review/', '/cms', '/cms/content', '/cms/new', '/cms/settings', '/guide', '/static/README.html'):
            code, body, _ = self.req(path, auth=False)
            self.assertEqual(code, 200)
            self.assertEqual(body, shell, path)
        self.assertEqual(shell.count(b'<aside class="side">'), 1)
        self.assertIn(b'<main id="app">', shell)
        self.assertEqual(self.req('/api/admin/cases', auth=False)[0], 401)

    def test_login_limits_csrf_logout_and_expiry(self):
        self.assertEqual(self.req('/api/admin/cases', auth=False)[0],401)
        self.assertEqual(self.req('/api/admin/cases', {}, auth=False)[0],401)
        self.assertEqual(self.req('/api/auth/login', {'password':PASSWORD},headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.req('/api/auth/login',raw=b'password=x',headers={'Content-Type':'text/plain'})[0],415)
        for _ in range(5):
            self.assertEqual(self.req('/api/auth/login', {'password':'wrong'})[0],401)
        self.assertEqual(self.req('/api/auth/login', {'password':PASSWORD})[0],429)
        cms_auth._attempts.clear()
        self.login()
        self.assertEqual(self.req('/api/admin/cases',{},headers={'X-CSRF-Token':''})[0],403)
        self.assertEqual(self.req('/api/admin/cases',{},headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.req('/api/auth/logout',{})[0],200)
        self.assertEqual(self.req('/api/admin/cases')[0],401)
        self.login()
        for session in cms_auth._sessions.values():
            session['expires']=0
        self.assertEqual(self.req('/api/admin/cases')[0],401)

    def test_workflow_revisions_rejection_unpublish_and_conflict(self):
        self.login()
        c = self.create(notes='private editorial note')
        self.assertEqual(c['status'],'draft')
        self.assertEqual(self.req('/api/cases',auth=False)[1]['cases'],[])
        self.assertEqual(self.req('/api/cases/'+c['id'],auth=False)[0],404)
        self.assertEqual(self.req('/api/admin/cases/'+c['id']+'/approve',{'_version':c['_version']})[0],409)
        c = self.action(c,'submit')
        self.assertEqual(self.req('/api/cases',auth=False)[1]['cases'],[])
        self.assertEqual(self.req('/api/admin/cases/'+c['id']+'/reject',{'_version':c['_version'],'note':''})[0],400)
        c = self.action(c,'reject',note='Add more detail')
        self.assertEqual(c['status'],'rejected')
        c = self.action(c,'submit')
        c = self.action(c,'approve')
        public = self.req('/api/cases/'+c['id'],auth=False)[1]
        for field in ('notes','review_log','_version','revision','discovery','origin'):
            self.assertNotIn(field,public)
        version=c['_version']
        code, updated,_=self.req('/api/admin/cases/'+c['id'],{'title':'Second version','_version':version},method='PUT')
        self.assertEqual(code,200)
        self.assertEqual(updated['status'],'draft')
        self.assertEqual(self.req('/api/cases/'+c['id'],auth=False)[1]['title'],'First version')
        self.assertEqual(self.req('/api/admin/cases/'+c['id'],{'title':'stale','_version':version},method='PUT')[0],409)
        updated=self.action(updated,'submit')
        updated=self.action(updated,'reject',note='Not ready')
        self.assertEqual(self.req('/api/cases/'+c['id'],auth=False)[1]['title'],'First version')
        updated=self.action(updated,'submit')
        updated=self.action(updated,'approve')
        self.assertEqual(self.req('/api/cases/'+c['id'],auth=False)[1]['title'],'Second version')
        updated=self.action(updated,'unpublish')
        self.assertEqual(updated['status'],'archived')
        self.assertEqual(self.req('/api/cases/'+c['id'],auth=False)[0],404)
        self.action(self.action(updated,'submit'),'approve')
        self.assertEqual(len(store.load_cases()),1)
        self.assertTrue(store.load_cases()[0]['review_log'])

    def upload_image(self, color):
        buf=io.BytesIO()
        Image.new('RGB',(48,32),color).save(buf,format='PNG')
        code,data,_=self.req('/api/admin/uploads',method='POST',raw=buf.getvalue(),headers={'Content-Type':'application/octet-stream','X-Upload-Kind':'cover','X-File-Name':'cover.png'})
        self.assertEqual(code,201,data)
        return data['url']

    def test_legacy_delete_requires_archive_auth_and_current_version(self):
        self.login()
        c = self.create(source={'url': 'https://x.com/test/status/1234567890'})
        path = '/api/admin/cases/' + c['id'] + '/delete'
        def remove(item, **kwargs):
            return self.req(path, {'_version': item['_version']}, **kwargs)[0]
        self.assertEqual(remove(c, auth=False), 401)
        self.assertEqual(remove(c, headers={'X-CSRF-Token': ''}), 403)
        self.assertEqual(remove(c, headers={'Origin': 'https://other.example'}), 403)
        self.assertEqual(remove(c), 409)  # Draft
        c = self.action(c, 'submit')
        self.assertEqual(remove(c), 409)  # Pending
        c = self.action(c, 'reject', note='Needs changes')
        self.assertEqual(remove(c), 409)  # Rejected
        c = self.action(self.action(c, 'submit'), 'approve')
        self.assertEqual(remove(c), 409)  # Published
        _, revision, _ = self.req('/api/admin/cases/' + c['id'],
                                  {'title': 'Unapproved revision', '_version': c['_version']}, method='PUT')
        self.assertEqual(remove(revision), 409)  # Live removal needs explicit confirmation
        archived = self.action(revision, 'unpublish')
        self.assertEqual(remove(revision), 409)  # Stale version
        self.assertEqual(remove(archived), 200)
        self.assertEqual(remove(archived), 404)
        self.assertEqual(self.req('/api/admin/cases/' + c['id'])[0], 404)
        self.assertEqual(self.req('/api/cases/' + c['id'], auth=False)[0], 404)
        self.assertEqual(self.req('/api/admin/cases')[1]['cases'], [])
        self.assertIn('x.com/status/1234567890', store.known_urls())

    def test_direct_delete_confirms_live_versions_and_private_drafts(self):
        self.login()
        for status in ('draft', 'pending', 'rejected', 'published', 'revision'):
            with self.subTest(status=status):
                c = self.create()
                if status != 'draft':
                    c = self.action(c, 'submit')
                if status == 'rejected':
                    c = self.action(c, 'reject', note='Needs changes')
                if status in ('published', 'revision'):
                    c = self.action(c, 'approve')
                if status == 'revision':
                    _, c, _ = self.req('/api/admin/cases/' + c['id'], {'title':'New title', '_version':c['_version']}, method='PUT')
                path = '/api/admin/cases/' + c['id'] + '/delete'
                payload = {'_version':c['_version'], 'confirm_delete':True}
                if c['live_status'] == 'published':
                    self.assertEqual(self.req(path, payload)[0], 409)
                    self.assertEqual(self.req('/api/cases/' + c['id'], auth=False)[0], 200)
                    payload['remove_live'] = True
                self.assertEqual(self.req(path, payload)[0], 200)
                self.assertEqual(self.req('/api/cases/' + c['id'], auth=False)[0], 404)

    def test_ai_directory_admin_public_version_and_reference_integrity(self):
        admin, public = '/api/admin/ai-directory', '/api/ai-directory'
        code, db, _ = self.req(public, auth=False)
        self.assertEqual(code, 200)
        self.assertNotIn('version', db)
        self.assertEqual(self.req(admin, auth=False)[0], 401)
        self.login()
        initial = self.req(admin)[1]
        add = {'kind':'category', 'action':'save', 'name':'AI测试', 'version':initial['version']}
        self.assertEqual(self.req(admin, add, headers={'X-CSRF-Token':''})[0], 403)
        code, db, _ = self.req(admin, add)
        self.assertEqual(code, 200)
        cat = db['categories'][-1]
        self.assertEqual(cat['name'], 'AI 测试')
        self.assertEqual(self.req(admin, add)[0], 409)
        item = {'kind':'entry','action':'save','name':'Demo工具','url':'javascript:alert(1)','category':cat['id'],'version':db['version']}
        self.assertEqual(self.req(admin,item)[0], 400)
        item['url']='https://example.com/demo'
        code, db, _ = self.req(admin, item)
        self.assertEqual(code, 200)
        eid = db['entries'][-1]['id']
        self.assertEqual(self.req(admin, {'kind':'category','action':'delete','id':cat['id'],'version':db['version']})[0], 409)
        code, db, _ = self.req(admin, {'kind':'entry','action':'feature','id':eid,'featured':True,'version':db['version']})
        self.assertEqual(code, 200)
        self.assertTrue(self.req(public,auth=False)[1]['entries'][-1]['featured'])
        for kind, target in [('entry',eid),('category',cat['id'])]:
            code, db, _ = self.req(admin, {'kind':kind,'action':'delete','id':target,'version':db['version']})
            self.assertEqual(code, 200)
        self.assertNotIn(eid, [x['id'] for x in self.req(public,auth=False)[1]['entries']])

    def test_delete_does_not_remove_shared_media_or_concurrently_resubmitted_content(self):
        self.login()
        cover = self.upload_image('green')
        first = self.create(type='graphic', media={'kind':'image', 'thumbnail':cover})
        other = self.create(type='graphic', media={'kind':'image', 'thumbnail':cover})
        first = self.action(self.action(first, 'submit'), 'approve')
        other = self.action(self.action(other, 'submit'), 'approve')
        archived = self.action(first, 'unpublish')
        path = '/api/admin/cases/' + first['id'] + '/delete'
        pending = self.action(archived, 'submit')
        self.assertEqual(self.req(path, {'_version':archived['_version']})[0], 409)
        self.assertEqual(self.req(path, {'_version':pending['_version']})[0], 409)
        archived = self.action(self.action(pending, 'approve'), 'unpublish')
        self.assertEqual(self.req(path, {'_version':archived['_version']})[0], 200)
        self.assertEqual(self.req(cover, auth=False)[0], 200)
        self.assertEqual([c['id'] for c in store.load_cases()], [other['id']])

    def test_media_draft_revision_and_archived_access(self):
        self.login()
        first=self.upload_image('red')
        self.assertEqual(self.req(first,auth=False)[0],404)
        self.assertEqual(self.req(first)[0],200)
        c=self.create(type='graphic',media={'kind':'image','thumbnail':first})
        c=self.action(self.action(c,'submit'),'approve')
        code,_,hdr=self.req(first,auth=False)
        self.assertEqual(code,200)
        self.assertEqual(hdr['Cache-Control'],'no-store')
        second=self.upload_image('blue')
        code,c,_=self.req('/api/admin/cases/'+c['id'],{'media':{'kind':'image','thumbnail':second},'_version':c['_version']},method='PUT')
        self.assertEqual(code,200)
        self.assertEqual(self.req(first,auth=False)[0],200)
        self.assertEqual(self.req(second,auth=False)[0],404)
        c=self.action(self.action(c,'submit'),'approve')
        self.assertEqual(self.req(first,auth=False)[0],404)
        self.assertEqual(self.req(second,auth=False)[0],200)
        self.action(c,'unpublish')
        self.assertEqual(self.req(second,auth=False)[0],404)

    def test_validation_and_invalid_uploads(self):
        self.login()
        invalid=[{'title':[]},{'type':'bad'},{'tags':'bad'},{'media':{'thumbnail':'javascript:alert(1)'}},{'source':{'url':'data:text/html,bad'}},{'assets':[{'name':'x','url':'//evil.example'}]},{'status':'published'},{'media':{'thumbnail':'/media/%2e%2e/data/token.txt'}}]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.req('/api/admin/cases',payload)[0],400)
        c=self.create(title='',category='')
        self.assertEqual(self.req('/api/admin/cases/'+c['id']+'/submit',{'_version':c['_version']})[0],400)
        self.assertEqual(self.req('/api/admin/uploads',method='POST',raw=b'bad',headers={'Content-Type':'application/octet-stream','X-Upload-Kind':'cover','X-File-Name':'bad.png'})[0],400)
        self.assertEqual(self.req('/api/admin/uploads',method='POST',raw=b'<svg/>',headers={'Content-Type':'application/octet-stream','X-Upload-Kind':'cover','X-File-Name':'bad.svg'})[0],400)
        self.assertEqual(self.req('/static/%2e%2e/data/cms_password.json',auth=False)[0],400)

    def test_video_upload_and_public_range_playback(self):
        self.login()
        video = os.path.join(self.temp.name, 'sample.mp4')
        subprocess.run([mediautil.FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=gray:s=160x90:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video],
                       check=True, capture_output=True, timeout=30)
        code, uploaded, _ = self.req('/api/admin/uploads', method='POST', raw=Path(video).read_bytes(),
                                    headers={'Content-Type':'application/octet-stream','X-Upload-Kind':'video','X-File-Name':'sample.mp4'})
        self.assertEqual(code, 201, uploaded)
        media = uploaded['media']
        for key in ('thumbnail', 'video', 'preview'):
            self.assertEqual(self.req(media[key],auth=False)[0],404)
        c = self.create(type='video',media=media)
        self.action(self.action(c,'submit'),'approve')
        code, data, headers = self.req(media['video'],auth=False,headers={'Range':'bytes=0-99'})
        self.assertEqual(code,206)
        self.assertEqual(len(data),100)
        self.assertTrue(headers['Content-Range'].startswith('bytes 0-99/'))
        self.assertEqual(self.req(media['thumbnail'],auth=False)[0],200)
        self.assertEqual(self.req('/static/README.md',auth=False)[0],200)

    def test_password_change_invalidates_sessions(self):
        self.login()
        new='new-secure-password-12345'
        self.assertEqual(self.req('/api/auth/password',{'current_password':'bad','new_password':new})[0],401)
        self.assertEqual(self.req('/api/auth/password',{'current_password':PASSWORD,'new_password':'short'})[0],400)
        self.assertEqual(self.req('/api/auth/password',{'current_password':PASSWORD,'new_password':new})[0],200)
        self.assertEqual(self.req('/api/admin/cases')[0],401)
        self.assertEqual(self.req('/api/auth/login',{'password':PASSWORD})[0],401)
        self.assertEqual(self.req('/api/auth/login',{'password':new})[0],200)
        self.assertEqual(os.stat(cms_auth.password_path()).st_mode & 0o777,0o600)
        self.assertNotIn(new,Path(cms_auth.password_path()).read_text())


if __name__ == '__main__':
    unittest.main()
