"""Render selected Drive reports without fetching or copying video bytes.

Input: a JSON array of {date, file:{id,url,title}, report, sourcePage, cover,
embeds, assets, attachmentLinks}. Assets map Markdown paths to local files;
attachmentLinks map analysis attachments to verified Google Drive file URLs.
The original Markdown is retained verbatim. Missing relative attachments are
labelled in the reader, never silently converted to broken local URLs.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'static/motion-log'


def import_reports(source):
    rows = json.loads(source.read_text())
    catalog = []
    renderer = MarkdownIt('commonmark', {'html': False}).enable('table')
    for row in rows:
        raw = row['report']
        slug = row['date'] + '-' + Path(row['file']['title']).stem.lower()
        dest = DEST / slug
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'report.md').write_bytes(raw.encode('utf-8'))
        doc = BeautifulSoup(renderer.render(raw), 'html.parser')
        title = row.get('title') or re.sub(r'^\d+\s*[|｜]\s*|\s*动态视频拆解$', '', doc.h1.get_text()).strip()
        doc.h1.decompose()
        intro = doc.find('p').get_text()
        fields = {}
        for tr in doc.select('table tr'):
            cells = tr.find_all('td')
            if len(cells) == 2:
                fields.setdefault(cells[0].get_text().strip(), cells[1].get_text().strip())
        embeds = [url for url in row.get('embeds', []) if url and urlsplit(url).scheme == 'https'
                  and urlsplit(url).hostname in {'player.vimeo.com', 'framerate.tv'}]
        if not embeds:
            raise ValueError(f'No verified original embed for {slug}')
        missing = missing_images = image_count = representative_count = external_count = 0
        assets = row.get('assets', {})
        attachment_links = row.get('attachmentLinks', {})

        def local_asset(url):
            mapped = assets.get(unquote(url))
            if not mapped:
                return None
            path = (dest / mapped).resolve()
            if not path.is_relative_to(dest.resolve()) or not path.is_file():
                raise ValueError(f'Missing or invalid report asset: {slug}/{mapped}')
            return mapped

        for image in doc.find_all('img'):
            if not urlsplit(image.get('src', '')).scheme:
                mapped = local_asset(image.get('src', ''))
                if mapped:
                    image['src'] = mapped
                    image['data-motion-asset'] = mapped
                    image['loading'] = 'lazy'
                    image['decoding'] = 'async'
                    with Image.open(dest / mapped) as source_image:
                        image['width'], image['height'] = source_image.size
                    full = doc.new_tag('a', attrs={'href': mapped, 'data-motion-asset': mapped,
                        'target': '_blank', 'rel': 'noopener', 'class': 'motion-keyframe',
                        'aria-label': image.get('alt', '关键画面') + '，查看原图'})
                    image.wrap(full)
                    image_count += 1
                    continue
                label = image.get('alt', '关键画面')
                figure = doc.new_tag('span', attrs={'class': 'motion-missing-image'})
                figure.string = label + ' · 原关键帧图片未收录'
                image.replace_with(figure)
                missing += 1
                missing_images += 1
        for a in doc.find_all('a'):
            if a.has_attr('data-motion-asset'):
                continue
            href = a.get('href', '')
            parsed = urlsplit(href)
            mapped = local_asset(href) if not parsed.scheme else None
            external = attachment_links.get(unquote(href))
            if mapped:
                a['href'] = mapped
                a['data-motion-asset'] = mapped
                a['target'] = '_blank'
                a['rel'] = 'noopener'
                if unquote(href).startswith('../frames/'):
                    representative_count += 1
            elif external:
                target = urlsplit(external)
                if target.scheme != 'https' or target.hostname != 'drive.google.com':
                    raise ValueError(f'Invalid Drive attachment URL: {slug}/{href}')
                a['href'] = external
                a['target'] = '_blank'
                a['rel'] = 'noopener noreferrer'
                a['title'] = '在 Google Drive 中打开原始分析附件'
                external_count += 1
            elif parsed.scheme in {'https', 'http'}:
                a['target'] = '_blank'
                a['rel'] = 'noopener noreferrer'
            elif '../videos/' in href:
                a['href'] = '#motion-player'
                a.string = '播放原片'
            else:
                a.name = 'span'
                a.attrs = {'class': 'motion-missing-attachment', 'title': '此分析附件尚未收录到站点'}
                a.append('（未收录）')
                missing += 1
        toc = []
        for i, heading in enumerate(doc.select('h2, h3')):
            heading['id'] = f'section-{i + 1}'
            if heading.name == 'h2':
                toc.append({'id': heading['id'], 'title': heading.get_text()})
        for table in doc.find_all('table'):
            first_header = table.find('th')
            if first_header and first_header.get_text().strip() == '#':
                table['class'] = 'motion-shot-index'
            wrap = doc.new_tag('div', attrs={'class': 'motion-table', 'tabindex': '0', 'role': 'region', 'aria-label': '报告表格，可横向滚动'})
            table.wrap(wrap)
        (dest / 'report.html').write_text(str(doc))
        catalog.append({
            'id': slug, 'title': title, 'date': row['date'], 'intro': intro,
            'brand': fields.get('品牌方', ''), 'creator': fields.get('制作方', ''),
            'duration': fields.get('时长', ''), 'spec': fields.get('规格', ''),
            'cover': row.get('cover', '').replace('http://', 'https://', 1),
            'embed': embeds[0], 'sourcePage': row['sourcePage'],
            'reportSource': row['file']['url'], 'reportFileId': row['file']['id'],
            'sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'missingAttachments': missing, 'missingImages': missing_images,
            'keyframeCount': image_count, 'toc': toc,
            'representativeFrameCount': representative_count,
            'externalAttachments': external_count,
        })
    catalog.sort(key=lambda x: x['date'], reverse=True)
    (DEST / 'index.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'reports': len(catalog), 'titles': [x['title'] for x in catalog]}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    import_reports(parser.parse_args().source)
