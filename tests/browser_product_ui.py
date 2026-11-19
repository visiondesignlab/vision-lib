"""Verify real screenshot downloads, Lab controls and Pages paths on disposable data.

PATH="$PWD/.venv/bin:$PATH" BROWSER_CHANNEL=chrome .venv/bin/python tests/browser_product_ui.py
Pass --pages-url http://127.0.0.1:8794/vision-lib for a built Pages preview too.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops
from playwright.sync_api import expect, sync_playwright
from browser_routes import fixture

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'static/assets/viaim/product-ui'
OUTPUT = ROOT / 'output/product-ui-review'
CATALOG = json.loads((ASSETS / 'catalog.json').read_text())


def check(browser, base, width, pages=False):
    context = browser.new_context(viewport={'width': width, 'height': 1000}, accept_downloads=True)
    context.route('https://**/*', lambda route: route.abort())
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    route = base + '/assets/brand?section=product-ui'
    page.goto(route)
    cards = page.locator('.ui-shot-card')
    expect(cards).to_have_count(6)
    preview = page.locator('.ui-preview-stage')

    def ready():
        expect(preview).to_have_attribute('aria-busy', 'false',timeout=15000)
        expect(preview).to_be_enabled()
        page.wait_for_function("document.querySelector('.ui-preview-stage img')?.naturalWidth > 0")

    def select(label, option):
        page.get_by_role('button', name=label, exact=True).click()
        page.get_by_role('menuitemradio', name=option, exact=True).click()
        ready()

    def download(locator, destination):
        with page.expect_download() as event:
            locator.click()
        result = event.value
        result.save_as(OUTPUT / destination)
        return (OUTPUT / destination).read_bytes(), result.suggested_filename

    ready()
    assert cards.first.locator('.ui-shot-image').bounding_box()['height'] > 200
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    raw, filename = download(page.locator('[data-ui-action=download]'), f'{width}-raw.png')
    source = (ASSETS / CATALOG['items'][0]['locales']['zh-Hans']['src']).read_bytes()
    assert raw == source, 'Native @3x was changed'
    assert 'original@3x.png' in filename
    page.emulate_media(reduced_motion='reduce')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=OUTPUT / f'{"pages" if pages else "local"}-{width}.png', full_page=True, animations='disabled')
    page.emulate_media(reduced_motion='no-preference')

    # Selection survives language changes and ZIP uses one captured configuration.
    cards.nth(0).locator('input').check()
    cards.nth(1).locator('input').check()
    select('截图语言', 'English')
    expect(cards.nth(0).locator('input')).to_be_checked()
    expect(page.locator('.ui-selection-count')).to_have_text('已选择 2 张 · English')
    select('导出样式', 'Mockup · 有底部阴影')
    for mode, height in [('shadow', 2961), ('clean', 2928)]:
        if mode == 'clean':
            select('导出样式', 'Mockup · 无底部阴影')
        body, _ = download(page.locator('[data-ui-action=download]'), f'{width}-{mode}.png')
        image = Image.open(io.BytesIO(body)).convert('RGBA')
        assert image.size == (1428, height)
        for box in [(0,0,1428,1),(0,height-1,1428,height),(0,0,1,height),(1427,0,1428,height)]:
            assert image.crop(box).getchannel('A').getextrema()[1] == 0, 'Clipped mockup edge'
        source_image = Image.open(ASSETS / CATALOG['items'][0]['locales']['en']['src']).convert('RGBA')
        assert ImageChops.difference(image.crop((324,336,1044,2436)), source_image.crop((240,240,960,2340))).getbbox() is None, 'Screen was covered or changed'
        if mode == 'shadow':
            assert image.crop((0,2904,1428,2937)).getchannel('A').getextrema()[1] > 0
    select('导出样式', 'Mockup · 有底部阴影')
    select('导出倍率', '@2x')
    body, _ = download(page.locator('[data-ui-action=download]'), f'{width}-2x.png')
    assert Image.open(io.BytesIO(body)).size == (952,1974)
    body, _ = download(page.locator('[data-ui-action=zip]'), f'{width}-selected.zip')
    with ZipFile(io.BytesIO(body)) as archive:
        assert archive.testzip() is None
        images = [name for name in archive.namelist() if name.endswith('.png')]
        assert len(images) == 2 and all('_en_mockup-shadow@2x' in name for name in images)
        assert all(Image.open(io.BytesIO(archive.read(name))).size == (952,1974) for name in images)

    # The shared overlay must open, zoom, close with Escape and restore focus.
    preview.click()
    expect(page.locator('#overlay')).to_be_visible()
    page.get_by_role('button', name='放大', exact=True).click()
    expect(page.locator('.asset-zoom-value')).to_have_text('125%')
    page.keyboard.press('Escape')
    expect(page.locator('#overlay')).to_be_hidden()
    expect(preview).to_be_focused()
    search = page.get_by_role('searchbox', name='搜索产品界面')
    search.fill('不存在')
    expect(cards).to_have_count(0)
    expect(page.get_by_text('没有匹配的产品界面', exact=True)).to_be_visible()
    search.fill('翻译')
    expect(cards).to_have_count(2)
    page.locator('[data-ui-action=all]').click()
    expect(page.locator('.ui-selection-count')).to_have_text('已选择 3 张 · English')
    page.locator('[data-ui-action=clear]').click()
    expect(page.locator('[data-ui-action=zip]')).to_be_disabled()
    search.fill('')
    select('截图语言', '日本語')
    select('导出样式', '原生截图')
    select('导出倍率', '@3x · 默认')
    body, _ = download(page.locator('[data-ui-action=download]'), f'{width}-ja.png')
    assert body == (ASSETS / CATALOG['items'][0]['locales']['ja']['src']).read_bytes()
    page.reload()
    ready()
    expect(page.get_by_role('button', name='截图语言', exact=True)).to_have_text('日本語')
    assert 'locale=ja' in page.url
    page.locator('.brand-assets a[href*="section=visual-assets"]').click()
    expect(page.locator('#brandLogoGallery')).to_be_visible()
    page.get_by_role('link', name='产品界面', exact=True).click()
    ready()
    assert 'locale=ja' in page.url, 'Restored settings must remain refreshable/shareable'
    if width == 1440 and not pages:
        page.route('**/product-ui/catalog.json', lambda route: route.fulfill(status=503,body='Unavailable'))
        page.reload()
        expect(page.get_by_text('产品界面暂时无法加载',exact=True)).to_be_visible()
        page.unroute('**/product-ui/catalog.json')
        page.get_by_role('button',name='重新加载',exact=True).click()
        ready()
        # An unavailable screenshot cannot leave an old image labeled as the new export.
        page.route('**/P029.home.ja@3x.png',lambda route: route.fulfill(status=503,body='Unavailable'))
        page.reload()
        expect(page.locator('.ui-export-status')).to_have_attribute('role','alert')
        expect(preview).to_be_disabled()
        page.unroute('**/P029.home.ja@3x.png')
        page.reload()
        ready()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.goto(base + '/guide')
    guide = page.locator('[data-guide=brand-assets]')
    expect(guide).to_contain_text('产品界面 18 张')
    expect(guide).to_contain_text('默认下载无 mockup、无圆角的 @3x 原图')
    assert not errors, errors
    print(f'{"Pages" if pages else "Local"} {width}px: source bytes, mockup pixels/alpha/bounds, ZIP, locales, scale, shared viewer, filter, navigation passed')
    context.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages-url')
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for item in CATALOG['items']:
        for shot in item['locales'].values():
            assert hashlib.sha256((ASSETS / shot['src']).read_bytes()).hexdigest() == shot['sha256']
    with fixture() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv('BROWSER_CHANNEL') or None)
        for width in (1440,390):
            check(browser,base,width)
        if args.pages_url:
            check(browser,args.pages_url.rstrip('/'),1440,True)
        browser.close()
