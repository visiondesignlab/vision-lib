"""Keep every live navigation entry documented as the site grows."""
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Navigation(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.entries = {}
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'data-tab' in attrs:
            self.entries[attrs['data-tab']] = attrs


class GuideTests(unittest.TestCase):
    def test_navigation_coverage_and_in_place_entry(self):
        nav = Navigation((ROOT / 'static/index.html').read_text()).entries
        content = json.loads((ROOT / 'static/guide-content.json').read_text())
        guide = nav.pop('guide')
        self.assertEqual(guide['href'], '/guide')
        self.assertIn('data-link', guide)
        self.assertNotIn('target', guide)
        for key in nav:
            with self.subTest(section=key):
                self.assertIn(key, content, 'Document new navigation in guide-content.json')
                self.assertTrue(content[key].get('steps'), 'New functionality needs usage steps')
        self.assertEqual(set(nav), set(content), 'Remove instructions for retired navigation')

    def test_legacy_help_is_the_shared_shell(self):
        self.assertEqual((ROOT / 'static/README.html').read_text(), (ROOT / 'static/index.html').read_text())


if __name__ == '__main__':
    unittest.main()
