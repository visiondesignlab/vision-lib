"""Build the in-page slide gallery from the repository's editable PowerPoint."""
import io
import os
import platform
import posixpath
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}


def slide_titles(data):
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        presentation = ET.fromstring(package.read('ppt/presentation.xml'))
        relationships = ET.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
        targets = {rel.get('Id'): rel.get('Target') for rel in relationships}
        titles = []
        for slide in presentation.findall('p:sldIdLst/p:sldId', NS):
            target = targets[slide.get('{' + NS['r'] + '}id')]
            path = posixpath.normpath(posixpath.join('ppt', target)).lstrip('/')
            root = ET.fromstring(package.read(path))
            title = []
            heading_size = None
            for shape in root.findall('.//p:sp', NS):
                props = shape.find('p:nvSpPr/p:cNvPr', NS)
                name = props.get('name', '') if props is not None else ''
                placeholder = shape.find('p:nvSpPr/p:nvPr/p:ph', NS)
                is_title = placeholder is not None and placeholder.get('type') in ('title', 'ctrTitle')
                size = max((int(run.get('sz', 0)) for run in shape.findall('.//a:rPr', NS)), default=0)
                # HTML exports may split an emphasized part of a heading into a separate text shape.
                continuation = heading_size and size == heading_size and re.search(r'-span(?:-|$)', name)
                if is_title or re.search(r'-h[12](?:-|$)', name) or continuation:
                    title.extend(t.text for t in shape.findall('.//a:t', NS) if t.text)
                    heading_size = size
                else:
                    heading_size = None
            titles.append(''.join(title).strip() or f'第 {len(titles) + 1} 页')
    if not titles:
        raise ValueError('PowerPoint example contains no slides')
    return titles


def conversion_environment(work):
    env = os.environ.copy()
    if platform.system() == 'Darwin':
        # The bundled headless office has no default macOS font directories.
        config = ET.Element('fontconfig')
        for path in ('/System/Library/Fonts', '/Library/Fonts', Path.home() / 'Library/Fonts'):
            ET.SubElement(config, 'dir').text = str(path)
        ET.SubElement(config, 'cachedir').text = str(work / 'font-cache')
        config_file = work / 'fonts.conf'
        ET.ElementTree(config).write(config_file, encoding='utf-8')
        env['FONTCONFIG_FILE'] = str(config_file)
    return env


def presentation_assets(content, source_path, folder, prefix):
    titles = slide_titles(content)
    destination = folder / 'presentation'
    destination.mkdir(parents=True, exist_ok=True)
    filename = Path(source_path).name
    deck = destination / filename
    filenames = [f'slide-{i:02}.webp' for i in range(1, len(titles) + 1)]
    complete = (deck.is_file() and deck.read_bytes() == content
                and all((destination / name).is_file() for name in filenames))
    if not complete:
        with tempfile.TemporaryDirectory(dir=destination) as tmp:
            work = Path(tmp).resolve()
            source = work / 'example.pptx'
            source.write_bytes(content)
            subprocess.run(['soffice', '-env:UserInstallation=' + (work / 'profile').as_uri(),
                            '--headless', '--convert-to', 'pdf', '--outdir', str(work), str(source)],
                           check=True, timeout=120, env=conversion_environment(work))
            subprocess.run(['pdftoppm', '-scale-to', '1600', '-png', str(work / 'example.pdf'),
                            str(work / 'render')], check=True, timeout=180)
            pages = sorted(work.glob('render-*.png'), key=lambda page: int(page.stem.split('-')[-1]))
            if len(pages) != len(titles):
                raise ValueError(f'Expected {len(titles)} rendered slides, got {len(pages)}')
            for page, name in zip(pages, filenames):
                with Image.open(page) as image:
                    image.save(work / name, 'WEBP', lossless=True, method=4)
            for name in filenames:
                os.replace(work / name, destination / name)
            os.replace(source, deck)
    url = prefix + 'presentation/'
    samples = [{'label': title, 'url': url + name} for title, name in zip(titles, filenames)]
    return samples, {'name': '下载示例 PPTX', 'url': url + filename}
