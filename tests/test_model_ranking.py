import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import update_model_ranking as ranking


def language_table(legacy=False, missing_header=False, broken_provider=False):
    columns = ['模型', '上下文窗口', '开发商', 'Artificial Analysis Intelligence Index',
               '每任务成本 美元', '每任务耗时 分钟', '首个答案 Token（秒）', '进一步分析'] if legacy else [
                   '模型', 'Artificial Analysis Intelligence Index', '每任务成本 美元',
                   '每任务耗时 分钟', '首个答案 Token（秒）', '上下文窗口', '进一步分析']
    logo = '<img alt="Example logo" src="/img/logos/example.svg">' if not broken_provider else ''
    rows = []
    for i in range(30):
        values = {'模型': ('' if legacy else logo) + f'Model {i} Max', '上下文窗口': '1M',
                  '开发商': logo + 'Example', 'Artificial Analysis Intelligence Index': str(100 - i),
                  '每任务成本 美元': '$2.50', '每任务耗时 分钟': '--' if i == 1 else '40.9',
                  '首个答案 Token（秒）': '207.86', '进一步分析': f'<a href="/zh/models/model-{i}">Model</a>'}
        rows.append('<tr>' + ''.join('<td>' + values[c] + '</td>' for c in columns) + '</tr>')
    if missing_header:
        columns[columns.index('上下文窗口')] = '未知指标'
    return '<table><thead><tr>' + ''.join('<th>' + c + '</th>' for c in columns) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


class ModelRankingTests(unittest.TestCase):
    def test_legacy_and_merged_developer_layouts_have_identical_metrics(self):
        parsed = []
        for legacy in (True, False):
            logos = {}
            rows = ranking.extract(language_table(legacy), 'language', logos)
            self.assertEqual(len(rows), 30)
            self.assertEqual(logos, {'Example': '/img/logos/example.svg'})
            self.assertEqual(rows[0], {'model': 'Model 0 Max', 'provider': 'Example',
                'url': 'https://artificialanalysis.ai/zh/models/model-0', 'score': 100.0,
                'contextTokens': 1000000, 'costUSD': 2.5, 'durationMinutes': 40.9,
                'firstAnswerSeconds': 207.86})
            self.assertIsNone(rows[1]['durationMinutes'])
            parsed.append(rows)
        self.assertEqual(*parsed)

    def test_missing_metrics_or_developer_are_not_silently_accepted(self):
        for options in ({'missing_header': True}, {'broken_provider': True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                ranking.extract(language_table(**options), 'language', {})

    def test_duplicates_and_unsorted_scores_are_rejected(self):
        for html in [language_table().replace('Model 1 Max', 'Model 0 Max'),
                     language_table().replace('<td>99</td>', '<td>101</td>')]:
            with self.assertRaises(ValueError):
                ranking.extract(html, 'language', {})

    def test_failed_board_preserves_existing_snapshot_and_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = json.dumps({'date': '2026-11-13', 'boards': {'valid': True}})
            (root/'model-rankings.json').write_text(original)
            (root/'language.html').write_text(language_table())
            (root/'invalid.html').write_text('<html>Source unavailable</html>')
            args = ['update_model_ranking.py', '--language', str(root/'language.html'), '--as-of', '2026-11-17']
            for mode in ('image', 'video', 'speech'):
                args += ['--'+mode, str(root/'invalid.html')]
            with patch.object(ranking, 'STATIC', root), patch('sys.argv', args), self.assertRaises(ValueError):
                ranking.main()
            self.assertEqual((root/'model-rankings.json').read_text(), original)
            self.assertFalse((root/'model-rankings.tmp').exists())


if __name__ == '__main__':
    unittest.main()
