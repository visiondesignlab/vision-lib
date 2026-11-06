"""Publication boundaries and project-subdirectory routing, without private data."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages_build', ROOT / 'scripts/build_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


class PagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {
            'static/index.html': '<a href="/">Home</a><script src="/static/site.js"></script>',
            'static/site.js': '/* runtime */',
            'static/style.css': 'video{filter:url("/static/media-controls.svg#half")}',
            'static/assets/viaim/manifest.json': '{"href":"/static/brand.pdf"}',
            'static/README.html': "<script>fetch('/static/README.md')</script>",
            'static/cms.js': 'PRIVATE_CMS',
            'data/admin_token.txt': 'PRIVATE_TOKEN',
            'media/unpublished.png': 'PRIVATE_MEDIA',
            'publish/media/approved.png': 'PUBLIC_MEDIA',
            'publish/large-assets.json': '[]',
            'catalog/ai-directory.json': '{"categories":[],"entries":[]}',
            'docs/pages-guide.md': 'Public instructions',
        }
        for name, content in files.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.case = {'id': 'published-case', 'status': 'published', 'media': {'thumbnail': '/media/approved.png'}}
        self.snapshot()
        self.output = self.root / 'dist'

    def snapshot(self):
        (self.root / 'publish/cases.json').write_text(json.dumps({'cases': [self.case]}))

    def build(self, base='/vision-lib'):
        with patch.object(pages, 'ROOT', self.root):
            return pages.build(self.output, base)

    def test_publication_is_allowlisted(self):
        self.build()
        self.assertFalse((self.output / 'data').exists())
        self.assertFalse((self.output / 'media/unpublished.png').exists())
        self.assertFalse((self.output / 'static/cms.js').exists())
        self.assertTrue((self.output / 'media/approved.png').exists())

    def test_project_paths_and_direct_routes(self):
        self.build()
        shell = (self.output / 'c/published-case/index.html').read_text()
        self.assertIn('href="/vision-lib/"', shell)
        self.assertIn('"staticMode": true', shell)
        self.assertIn('src="/vision-lib/static/site.js"', shell)
        data = json.loads((self.output / 'public/cases.json').read_text())
        self.assertEqual(data['cases'][0]['media']['thumbnail'], '/vision-lib/media/approved.png')
        self.assertIn('/vision-lib/static/media-controls.svg#half', (self.output / 'static/style.css').read_text())
        self.assertEqual((self.output / 'submit/index.html').read_text(), shell)
        self.assertEqual((self.output / 'tools/ai-nav/index.html').read_text(), shell)
        self.assertEqual((self.output / 'tools/ai-models/index.html').read_text(), shell)
        self.assertEqual((self.output / 'tools/playground/index.html').read_text(), shell)
        self.assertEqual((self.output / 'assets/design/index.html').read_text(), shell)
        self.assertEqual((self.output / 'journal/index.html').read_text(), shell)
        self.assertEqual((self.output / 'academy/index.html').read_text(), shell)
        self.assertEqual(json.loads((self.output / 'public/ai-directory.json').read_text()), {'categories': [], 'entries': []})
        self.assertEqual((self.output / 'guide/index.html').read_text(), shell)
        self.assertEqual((self.output / 'static/README.html').read_text(), shell)

    def test_unpublished_and_internal_fields_rejected(self):
        for mutation in ({'status': 'draft'}, {'notes': 'PRIVATE_NOTE'}, {'revision': {}}):
            with self.subTest(mutation=mutation):
                self.case = {'id': 'published-case', 'status': 'published', **mutation}
                self.snapshot()
                with self.assertRaises(ValueError):
                    self.build()

    def test_does_not_erase_unowned_output(self):
        self.output.mkdir()
        (self.output / 'keep.txt').write_text('user file')
        with self.assertRaises(ValueError):
            self.build()
        self.assertTrue((self.output / 'keep.txt').exists())

    def test_missing_public_media_fails_the_build(self):
        (self.root / 'publish/media/approved.png').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing published asset'):
            self.build()

    def test_release_asset_download_and_integrity(self):
        source = self.root / 'original.pdf'
        source.write_bytes(b'original release asset')
        asset = {'path': 'static/brand.pdf', 'name': 'brand.pdf', 'url': source.as_uri(),
                 'bytes': source.stat().st_size, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        manifest = self.root / 'publish/large-assets.json'
        manifest.write_text(json.dumps([asset]))
        self.build()
        self.assertEqual((self.output / 'static/brand.pdf').read_bytes(), source.read_bytes())
        source.write_bytes(b'tampered release asset')
        with self.assertRaisesRegex(ValueError, 'integrity check failed'):
            self.build()

    def test_external_assets_are_not_copied_or_downloaded(self):
        (self.root / 'catalog/external-assets.json').write_text(json.dumps(['static/brand.pdf','static/film.mp4']))
        (self.root / 'static/brand.pdf').write_bytes(b'local backup')
        (self.root / 'static/film.mp4').write_bytes(b'local video backup')
        (self.root / 'publish/large-assets.json').write_text(json.dumps([{'path':'static/brand.pdf','url':'https://invalid.example/unused'}]))
        self.build()
        self.assertFalse((self.output / 'static/brand.pdf').exists())
        self.assertFalse((self.output / 'static/film.mp4').exists())
        self.assertTrue((self.root / 'static/brand.pdf').exists())

    def test_route_runtime_is_idempotent(self):
        runtime = (ROOT / 'static/site.js').read_text()
        script = 'global.window={VISION_CONFIG:{basePath:"/vision-lib",staticMode:true}};global.location={pathname:"/vision-lib/c/example/"};'
        script += runtime
        script += '''
const s=window.VisionSite,assert=require('node:assert/strict');
assert.equal(s.path('/c/example'),'/vision-lib/c/example');
assert.equal(s.path('/vision-lib/c/example'),'/vision-lib/c/example');
assert.equal(s.path('https://example.com/'),'https://example.com/');
assert.equal(s.path('//example.com/'),'//example.com/');
assert.equal(s.routePath(),'/c/example');
assert.equal(s.routePath('/vision-lib/'),'/');
'''
        subprocess.run(['node', '-e', script], check=True)


if __name__ == '__main__':
    unittest.main()
