"""Build the local four-tab model ranking snapshot from saved Artificial Analysis tables.

Requires beautifulsoup4. Pass the Chinese leaderboard HTML for each board and its
observation date. Only the resulting public snapshot and its display logos ship.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static/tools'
ORIGIN = 'https://artificialanalysis.ai'
LIMIT = 50
SOURCES = {
    'language': '/zh/leaderboards/models',
    'image': '/zh/image/leaderboard/text-to-image',
    'video': '/zh/video/leaderboard/text-to-video',
    'speech': '/zh/text-to-speech/leaderboard/provider-voice',
}


def number(text):
    if text.strip() in {'--', '—', '-', ''}:
        return None
    return float(text.strip().removeprefix('$').replace(',', ''))


def tokens(text):
    if number_or_missing := re.fullmatch(r'([\d,.]+)([KMB]?)', text.upper()):
        scale = {'': 1, 'K': 1000, 'M': 10**6, 'B': 10**9}
        return int(number(number_or_missing[1]) * scale[number_or_missing[2]])
    if text in {'--','—','-',''}:
        return None
    raise ValueError(f'Unknown context window: {text}')


def logo_from(cell):
    img = cell.select_one('img[src]')
    if img is None:
        return '', ''
    loc = urlsplit(img['src'])
    path = parse_qs(loc.query).get('url', [loc.path])[0] if loc.path == '/_next/image' else loc.path
    if not re.fullmatch(r'/img/logos/[\w.-]+\.(svg|png|jpe?g|webp)', path):
        raise ValueError(f'Unexpected logo location {path!r}')
    return img.get('alt','').removesuffix(' logo'), path


def language_row(cells):
    model, context, provider, index, cost, duration, latency, _ = [td.get_text(' ',strip=True) for td in cells]
    href = cells[-1].select_one('a[href]')['href']
    if not href.startswith('/zh/models/'):
        raise ValueError(f'Invalid model link for {model}')
    return dict(model=model, url=urljoin(ORIGIN,href), provider=provider, score=number(index),
                contextTokens=tokens(context), costUSD=number(cost), durationMinutes=number(duration),
                firstAnswerSeconds=number(latency))


def media_row(cells, mode):
    text = [td.get_text(' ',strip=True) for td in cells]
    provider, _ = logo_from(cells[2])
    model = cells[2].select_one('span.font-medium').get_text(' ',strip=True)
    elo = re.match(r'^([\d,]+)\b', text[3])
    if not elo or not provider:
        raise ValueError(f'Missing Elo or developer for {model}')
    # Speech dates use English month names; the image and video views use Chinese.
    released = text[-2]
    match = re.fullmatch(r'(\d{4})年(\d{1,2})月', released)
    if match:
        released = f'{match[1]}-{int(match[2]):02}'
    elif released not in {'--','—','暂无'}:
        released = datetime.strptime(released.replace('Sept ', 'Sep '), '%b %Y').strftime('%Y-%m')
    else:
        released = None
    price = re.match(r'^US\$([\d,.]+)',text[-1])
    row = dict(model=model,provider=provider,score=number(elo[1]), votes=int(number(text[4])),
               range=text[1], released=released, price=number(price[1]) if price else None)
    if mode=='speech':
        count=re.search(r'\d+',text[5])
        row['voices']=int(count[0]) if count else None
    return row


def extract(html, mode, logos):
    expected = ['模型','上下文窗口','开发商','Artificial Analysis Intelligence Index','每任务成本','每任务耗时','首个答案','进一步分析'] if mode=='language' else ['', '范围', '模型', 'Elo', '样本数'] + (['Arena 语音','发布'] if mode=='speech' else ['发布日期']) + ['价格']
    soup = BeautifulSoup(html, 'html.parser')
    for table in soup.select('table'):
        headers = table.select('thead tr:last-child th')
        if len(headers)==len(expected) and all(h.get_text(' ',strip=True).startswith(t) for h,t in zip(headers, expected)):
            break
    else:
        raise ValueError(f'{mode}: Unexpected source columns')
    rows=[]
    for i,tr in enumerate(table.select('tbody tr')[:LIMIT],1):
        cells = tr.find_all('td',recursive=False)
        if mode!='language' and cells[0].get_text(strip=True)!=str(i):
            raise ValueError(f'{mode}: Source is not ordered by published rank')
        row = language_row(cells) if mode=='language' else media_row(cells,mode)
        _, logo = logo_from(cells[2])
        if logo:
            logos[row['provider']] = logo
        rows.append(row)
    if len(rows)<30 or len({r['model'] for r in rows})!=len(rows) or any(r['score'] is None for r in rows):
        raise ValueError(f'{mode}: Incomplete or duplicate entries')
    if any(a['score']<b['score'] for a,b in zip(rows,rows[1:])):
        raise ValueError(f'{mode}: Scores do not follow source order')
    return rows


def cache_logo(path):
    directory=STATIC/'ranking-logos/providers'
    directory.mkdir(parents=True,exist_ok=True)
    name=Path(path).name
    target=directory/name
    if not target.exists():
        raw=subprocess.check_output(['curl','-fsSL','--compressed','--retry','2','--max-time','15','--max-filesize','1800000',urljoin(ORIGIN,path)])
        if name.endswith('.svg'):
            if not ElementTree.fromstring(raw).tag.endswith('svg'):
                raise ValueError(f'Invalid SVG: {name}')
        else:
            from PIL import Image
            from io import BytesIO
            Image.open(BytesIO(raw)).verify()
        target.write_bytes(raw)
    return 'providers/'+name


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for mode in SOURCES:
        ap.add_argument('--'+mode,required=True,type=Path)
    ap.add_argument('--as-of',type=date.fromisoformat,required=True)
    args=ap.parse_args()
    boards={}
    logos={}
    for mode, source in SOURCES.items():
        rows=extract(getattr(args,mode).read_bytes(),mode,logos)
        boards[mode]={'source':urljoin(ORIGIN,source),'rows':rows}
    # Use the standalone infinity symbol, not the horizontal Meta wordmark.
    symbols = {'Meta': 'meta-color.svg'}
    paths=sorted({p for name,p in logos.items() if name not in symbols})
    with ThreadPoolExecutor(max_workers=6) as pool:
        filenames=dict(zip(paths,pool.map(cache_logo,paths)))
    data={'date':args.as_of.isoformat(),'providerLogos':{name:(symbols[name] if name in symbols else filenames[path]) for name,path in sorted(logos.items())},'boards':boards}
    output=STATIC/'model-rankings.json'
    temp=output.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
    os.replace(temp,output)
    print({name:len(board['rows']) for name,board in boards.items()})


if __name__=='__main__':
    main()
