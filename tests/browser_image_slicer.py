"""Per-image manual cuts and real ZIP exports, using an isolated browser/store."""
import os
import struct
import zlib
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright
from browser_routes import fixture


def png(width, height, color):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = (b'\0' + bytes(color) * width) * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def check(browser, base, width):
    context = browser.new_context(viewport={'width': width, 'height': 1000}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    context.route('https://**/*', lambda route: route.abort())
    page.goto(base + '/tools/image-slicer')
    page.locator('[data-mode=manual]').click()
    page.locator('#chunkHeight').fill('500')

    def upload(name, height, color):
        return {'name': name, 'mimeType': 'image/png', 'buffer': png(120, height, color)}

    def ready(name):
        expect(page.locator('.image-slicer')).to_have_attribute('aria-busy', 'false')
        expect(page.locator('#currentFileName')).to_have_text(name)
        expect(page.locator('.slicer-file-select[aria-pressed=true]')).to_have_count(1)

    def select(index, name):
        page.locator('.slicer-file-select').nth(index).click()
        ready(name)

    def cuts(values):
        for value in values:
            page.locator('#cutYInput').fill(str(value))
            page.locator('#addCutYBtn').click()

    def expect_cuts(values):
        assert page.locator('#cutList .cut-chip').evaluate_all(
            "els => els.map(el => Number(el.textContent.match(/全图 Y (\\d+)/)[1]))") == values

    page.locator('#fileInput').set_input_files([
        upload('first.png', 900, (220, 80, 50)), upload('second.png', 900, (40, 150, 180))])
    ready('first.png')
    cuts([300, 600])
    select(1, 'second.png')
    expect_cuts([])
    cuts([200, 700])
    select(0, 'first.png')
    expect_cuts([300, 600])
    page.locator('#loadPreviewBtn').click()
    ready('first.png')
    expect_cuts([300, 600])

    # Adding/removing a pending image must not discard the existing cuts.
    page.locator('#fileInput').set_input_files(upload('pending.png', 1000, (80, 90, 100)))
    ready('first.png')
    expect(page.locator('#fileCount')).to_have_text('3 张')
    page.locator('#sliceBtn').click()
    expect(page.locator('#status')).to_contain_text('pending.png')
    expect(page.locator('#status')).to_contain_text('未设置')
    page.get_by_role('button', name='移除 pending.png', exact=True).click()
    ready('first.png')
    expect_cuts([300, 600])

    # Clear only the active image, then restore its cuts.
    select(1, 'second.png')
    page.locator('#clearCutsBtn').click()
    expect_cuts([])
    page.locator('#sliceBtn').click()
    expect(page.locator('#status')).to_contain_text('second.png')
    expect(page.locator('#status')).to_contain_text('超过最大高度')
    select(0, 'first.png')
    expect_cuts([300, 600])
    select(1, 'second.png')
    cuts([200, 700])

    # Preview and export coordinates follow the same output scale for every image.
    page.locator('#targetWidth').fill('60')
    ready('second.png')
    expect_cuts([100, 350])
    select(0, 'first.png')
    expect_cuts([150, 300])
    page.locator('#targetWidth').fill('0')
    expect(page.locator('#previewFrame')).to_be_hidden()
    page.locator('#targetWidth').fill('')
    ready('first.png')
    expect_cuts([300, 600])
    select(1, 'second.png')
    expect_cuts([200, 700])

    page.locator('#sliceBtn').click()
    expect(page.locator('#status')).to_contain_text('完成：共切出 6 张切片')
    expect(page.locator('.result-card')).to_have_count(2)
    with page.expect_download() as download:
        page.locator('#downloadZipBtn').click()
    with ZipFile(download.value.path()) as archive:
        assert len(archive.namelist()) == 6
        for name, bounds in [('first', [(0, 300), (300, 600), (600, 900)]),
                             ('second', [(0, 200), (200, 700), (700, 900)])]:
            files = sorted(n for n in archive.namelist() if n.startswith(name + '_'))
            assert len(files) == 3, files
            for filename, (top, bottom) in zip(files, bounds):
                assert f'_y{top:05}-{bottom:05}.png' in filename
                assert struct.unpack('>II', archive.read(filename)[16:24]) == (120, bottom - top)

    # Editing invalidates old downloadable results. Switching modes preserves cuts.
    page.locator('#cutList .chip-remove').first.click()
    expect(page.locator('#downloadZipBtn')).to_be_disabled()
    cuts([200])
    page.locator('[data-mode=auto]').click()
    page.locator('#sliceBtn').click()
    expect(page.locator('#status')).to_contain_text('完成：共切出 4 张切片')
    page.locator('[data-mode=manual]').click()
    ready('second.png')
    expect_cuts([200, 700])
    select(0, 'first.png')
    page.get_by_role('button', name='移除 first.png', exact=True).click()
    ready('second.png')
    expect_cuts([200, 700])
    page.locator('#clearBtn').click()
    expect(page.locator('#fileCount')).to_have_text('未选择')
    expect(page.locator('#previewFrame')).to_be_hidden()
    expect(page.locator('#downloadZipBtn')).to_be_disabled()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    context.close()
    print(f'{width}px: single selection, independent cuts, add/remove/clear, resize, manual ZIP and auto mode passed')


if __name__ == '__main__':
    with fixture() as base, sync_playwright() as p:
        browser = p.chromium.launch(channel=os.getenv('BROWSER_CHANNEL') or None)
        for width in (1440, 390):
            check(browser, base, width)
        browser.close()
