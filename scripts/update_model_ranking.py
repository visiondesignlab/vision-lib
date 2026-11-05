"""Refresh the local top 30 from a saved Artificial Analysis leaderboard page (beautifulsoup4)."""
import argparse
from datetime import date
from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_directory
import store

SOURCE = 'https://artificialanalysis.ai/zh/leaderboards/models'
LIMIT = 30


def metric(text):
    if text in {'--', '—', '-', ''}:
        return None
    return float(text.removeprefix('$').replace(',', ''))


def context_tokens(text):
    if text in {'--', '—', '-', ''}:
        return None
    match = re.fullmatch(r'([\d,.]+)([KMB]?)', text)
    if not match:
        raise ValueError(f'Unknown context window: {text}')
    scale = {'': 1, 'K': 1000, 'M': 10**6, 'B': 10**9}
    return int(metric(match[1]) * scale[match[2]])


def extract(html):
    soup = BeautifulSoup(html, 'html.parser')
    expected = ['模型', '上下文窗口', '开发商', 'Artificial Analysis Intelligence Index',
                '每任务成本', '每任务耗时', '首个答案', '进一步分析']
    for table in soup.select('table'):
        headers = table.select('thead tr:last-child th')
        if len(headers) == len(expected) and all(h.get_text(' ', strip=True).startswith(prefix)
                                                for h, prefix in zip(headers, expected)):
            break
    else:
        raise ValueError('Leaderboard columns have changed; verify the source before updating.')
    rows = []
    for tr in table.select('tbody tr')[:LIMIT]:
        cells = tr.find_all('td', recursive=False)
        model, context, provider, index, cost, duration, latency, _ = [c.get_text(' ', strip=True) for c in cells]
        href = cells[-1].select_one('a[href]')['href']
        if not href.startswith('/zh/models/') or not model:
            raise ValueError(f'Invalid model link for {model}')
        rows.append(dict(model=model, url=urljoin(SOURCE, href), provider=provider, score=metric(index),
                         contextTokens=context_tokens(context), costUSD=metric(cost),
                         durationMinutes=metric(duration), firstAnswerSeconds=metric(latency)))
    if len({r['url'] for r in rows}) != LIMIT or any(r['score'] is None for r in rows):
        raise ValueError('Source does not contain 30 distinct ranked models with scores.')
    if any(a['score'] < b['score'] for a, b in zip(rows, rows[1:])):
        raise ValueError('Source is not ordered by intelligence; check the selected sort.')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--as-of', type=date.fromisoformat, required=True, help='Snapshot date (YYYY-MM-DD)')
    args = parser.parse_args()
    snapshot = {'date': args.as_of.isoformat(), 'rows': extract(args.html.read_bytes())}
    with store.locked():
        db = ai_directory.load()
        entry = next(e for e in db['entries'] if e['category'] == 'model-rankings' and e['url'] == SOURCE)
        if entry.get('ranking') != snapshot:
            entry['ranking'] = snapshot
            db['version'] += 1
            store._write(str(Path(store.DATA) / 'ai-directory.json'), db)
    print(f'Local leaderboard: {len(snapshot["rows"])} models, {args.as_of}')


if __name__ == '__main__':
    main()
