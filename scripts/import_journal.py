"""Import the finished 有点意思 editions, without changing the source reports."""
import argparse
import base64
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
TITLE = re.compile(r'Vol\.(\d+) 有点意思 A Little Something')
FORMATS = {'jpeg': 'jpg', 'png': 'png', 'webp': 'webp', 'avif': 'avif', 'gif': 'gif'}


def import_issue(source, volume, directory):
    soup = BeautifulSoup(source.read_bytes().decode('utf-8'), 'html.parser')
    article = soup.select_one('main.page')
    if article is None or article.h1.get_text(strip=True) != source.stem:
        raise ValueError(f'{source.name}: unexpected article title')
    byline = article.select_one('.byline').get_text()
    issued = date.fromisoformat(re.search(r'\b\d{4}-\d{2}-\d{2}\b', byline)[0])
    first_story = next(article.h3.stripped_strings)
    headline = re.sub(r'^\d+[.)]\s*', '', first_story)
    intro = article.h2.find_next_sibling('p').get_text(strip=True)
    # Early editions put the marker and label in two adjacent spans.
    for heading in article.find_all('h2'):
        label = heading.get_text().strip()
        if label.startswith('●'):
            heading.string = '● ' + label[1:].lstrip()
    out = directory / str(volume)
    out.mkdir()
    images = []
    for comment in article.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()
    # Keep the edition's semantic text, order and layout classes; never import active markup.
    for node in article.find_all(True):
        tag, attrs = node.name, node.attrs.copy()
        node.attrs = {}
        if tag not in 'header h1 h2 h3 p span ul ol li strong em code figure img figcaption aside br a'.split():
            raise ValueError(f'{source.name}: unsupported element {tag}')
        classes = [c for c in attrs.get('class', []) if c in ('byline','mixed-script','verification','section-dot','source-url')]
        if classes:
            node['class'] = classes
        if 'source-url' in classes or tag == 'a':
            url = attrs.get('href') if tag == 'a' else node.get_text(strip=True)
            if url and urlsplit(url).scheme in ('https','http') and urlsplit(url).hostname:
                node.name = 'a'
                node.attrs.update(href=url, target='_blank', rel='noopener noreferrer')
        if tag == 'img':
            match = re.fullmatch(r'data:image/(jpeg|png|webp|avif|gif);base64,(.+)', attrs.get('src',''), re.S)
            if not match:
                raise ValueError(f'{source.name}: expected embedded editorial image')
            raw = base64.b64decode(match[2], validate=True)
            name = f'{len(images) + 1:02}.{FORMATS[match[1]]}'
            (out / name).write_bytes(raw)
            with Image.open(BytesIO(raw)) as image:
                node.attrs.update(src=name, alt=attrs.get('alt',''), width=str(image.width), height=str(image.height), loading='lazy', decoding='async')
                if not images:
                    preview = ImageOps.exif_transpose(image).convert('RGB')
                    preview.thumbnail((960, 640), Image.Resampling.LANCZOS)
                    preview.save(out / 'cover.webp', quality=84)
            images.append(name)
    # Connect only the primary film to its own editorial figure, never a making-of or sidebar link.
    for section in article.select('h2'):
        if '产品动态' not in section.get_text() or '视频' not in section.get_text():
            continue
        figure = None
        sources = []
        for node in section.find_next_siblings():
            if node.name == 'h2':
                break
            if node.name == 'figure' and figure is None:
                figure = node
            sources.extend(a['href'] for a in node.select('a[href]'))
        for url in sources:
            if figure is not None and urlsplit(url).hostname in {'player.vimeo.com','vimeo.com','www.youtube.com','youtu.be','framerate.tv'}:
                figure['data-film-source'] = url
                break
    if not images:
        raise ValueError(f'{source.name}: missing issue cover')
    (out / 'article.html').write_text(article.decode_contents(), encoding='utf-8')
    return dict(volume=volume, date=issued.isoformat(), headline=headline, intro=intro)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('daily', type=Path, help='Vision Design 设计日报/daily source directory')
    args = parser.parse_args()
    sources = [(int(match[1]), f) for f in args.daily.glob('*.html') if (match := TITLE.fullmatch(f.stem))]
    if not sources or len({vol for vol, _ in sources}) != len(sources):
        parser.error('No numbered editions or duplicate volume numbers.')
    target = ROOT / 'static/journal'
    target.mkdir(exist_ok=True)
    # Validate every volume before replacing any published article or its catalog.
    with tempfile.TemporaryDirectory(dir=target) as staging:
        stage = Path(staging)
        catalog = [import_issue(f, vol, stage) for vol, f in sorted(sources, reverse=True)]
        (stage / 'issues.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for entry in catalog:
            dirname = str(entry['volume'])
            dest = target / dirname
            if dest.exists():
                dest.rename(stage / (dirname + '.old'))
            (stage / dirname).rename(dest)
        (stage / 'issues.json').replace(target / 'issues.json')
    print(f'{len(catalog)} editions imported; latest Vol.{catalog[0]["volume"]} ({catalog[0]["date"]})')


if __name__ == '__main__':
    main()
