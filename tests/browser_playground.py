"""Playground user flows on a disposable store with a fake, isolated generation provider."""
import base64
import json
import os
from urllib.parse import urlsplit
from playwright.sync_api import expect, sync_playwright
from browser_routes import fixture
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=')

def check(browser,base,width):
    context=browser.new_context(viewport={'width':width,'height':900},accept_downloads=True)
    page=context.new_page(); errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    jobs={};calls=[];hold=False;reject=False;uploads=[]
    def route(r):
        nonlocal hold,reject
        path=urlsplit(r.request.url).path
        headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type, Authorization'}
        if r.request.method=='OPTIONS':return r.fulfill(status=204,headers=headers)
        data=r.request.post_data_json if r.request.post_data else {}
        if path=='/connect':result={'configured':True,'token':'qa-opaque-token'}
        elif path=='/connection':result={'configured':True}
        elif path=='/generate':
            calls.append(data)
            if reject:return r.fulfill(status=502,json={'error':'API Key 没有模型权限'},headers=headers)
            job='job-'+str(len(calls));jobs[job]={'status':'queued','plane':data['plane']};result={'requestId':job,'status':'queued'}
        elif path=='/status':
            result={'results':[{'requestId':i,'status':'queued' if hold else 'completed','images':[] if hold else [{'url':'https://media.fixture/one.png'},{'url':'https://media.fixture/two.png'}]} for i in data['ids']]}
        elif path=='/cancel':jobs[data['requestId']]['status']='canceled';result={'status':'canceled'}
        elif path=='/upload':result={'upload_url':'https://storage.fixture/put','public_url':'https://media.fixture/reference.png','upload_headers':{'Content-Type':'image/png'}}
        elif path=='/disconnect':result={'configured':False}
        else:raise AssertionError(path)
        r.fulfill(json=result,headers=headers)
    context.route('https://**/*',lambda r:r.abort())
    context.route('**/static/playground/config.json',lambda r:r.fulfill(json={'apiUrl':'https://playground.fixture'}))
    context.route('https://playground.fixture/**',route)
    context.route('https://media.fixture/**',lambda r:r.fulfill(body=PNG,content_type='image/png',headers={'Access-Control-Allow-Origin':'*'}))
    def upload(r):
        assert not r.request.header_value('Authorization');uploads.append(r.request.method)
        r.fulfill(status=200,headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type','Access-Control-Allow-Methods':'PUT, OPTIONS'})
    context.route('https://storage.fixture/**',upload)
    page.goto(base+'/tools/playground');expect(page.locator('.pg-composer')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('.pg-model').click();expect(page.locator('.pg-model-option')).to_have_count(8)
    page.locator('.pg-dialog-head button').click();page.locator('[data-surface=video]').click();page.locator('.pg-model').click()
    expect(page.locator('.pg-model-option')).to_have_count(30)
    page.locator('[aria-label="搜索模型"]').fill('motion');expect(page.locator('.pg-model-option')).to_have_count(2)
    page.locator('.pg-dialog-head button').click();page.locator('[data-surface=image]').click()
    page.locator('.pg-submit').click();expect(page.locator('dialog input[name=key]')).to_be_visible()
    page.locator('dialog input[name=key]').fill('qa-not-a-real-api-key');page.locator('dialog [type=submit]').click()
    expect(page.locator('dialog')).to_have_count(0)
    assert page.evaluate('JSON.stringify(localStorage)+JSON.stringify(sessionStorage)').find('qa-not-a-real-api-key')<0
    page.locator('[data-starter="0"]').click();prompt=page.locator('textarea').input_value()
    page.locator('.pg-submit').click();expect(page.locator('.pg-preview')).to_have_count(1,timeout=15000)
    assert len(calls)==1
    page.locator('.pg-preview').click();expect(page.locator('.pg-viewer .pg-count')).to_have_text('1 / 2')
    page.locator('.pg-next').click();expect(page.locator('.pg-viewer .pg-count')).to_have_text('2 / 2')
    page.locator('.pg-view-favorite').click();page.locator('.pg-reuse').click();expect(page.locator('textarea')).to_have_value(prompt)
    page.locator('[data-scope=favorites]').click();expect(page.locator('.pg-card')).to_have_count(1)
    page.locator('.pg-select-toggle').click();page.locator('[data-bulk=all]').click();page.locator('[data-bulk=delete]').click()
    expect(page.locator('.pg-card')).to_have_count(0);page.locator('.pg-undo button').click();expect(page.locator('.pg-card')).to_have_count(1)
    page.reload();expect(page.locator('.pg-card')).to_have_count(1)
    page.locator('[data-surface=video]').click();page.locator('[data-add=start]').click()
    page.locator('dialog input[type=file]').set_input_files({'name':'reference.png','mimeType':'image/png','buffer':PNG})
    expect(page.locator('.pg-attachment')).to_have_count(1,timeout=10000);assert 'PUT' in uploads
    page.locator('[data-remove]').click();expect(page.locator('.pg-attachment')).to_have_count(0)
    page.locator('textarea').fill('A camera orbit around a product');hold=True
    page.locator('.pg-submit').click();expect(page.locator('[data-run=cancel]')).to_have_count(1)
    page.locator('[data-run=cancel]').click();expect(page.get_by_text('已取消',exact=True)).to_be_visible()
    reject=True
    page.locator('.pg-submit').click();expect(page.get_by_text('API Key 没有模型权限',exact=True)).to_be_visible()
    page.goto(base+'/tools/ai-nav');expect(page.locator('.ai-directory')).to_be_visible()
    page.goto(base+'/tools/playground');expect(page.locator('textarea')).to_have_value('A camera orbit around a product')
    expect(page.locator('.pg-card')).to_have_count(3)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    print(f'{width}px: model catalog, credentials, generation, preview, favorite, reuse, delete/undo, upload, cancel, failure, persistence passed')
    context.close()

if __name__=='__main__':
    with fixture() as base,sync_playwright() as p:
        browser=p.chromium.launch(channel=os.getenv('BROWSER_CHANNEL') or None)
        for width in (1440,390):check(browser,base,width)
        browser.close()
