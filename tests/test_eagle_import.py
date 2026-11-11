"""Source grouping and retry safety for local Eagle intake."""
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

import cms_content
import store
from scripts.import_eagle import apply_manifest, scan, source_key


class EagleTests(unittest.TestCase):
    def test_canonical_source_keys_keep_post_identity(self):
        self.assertEqual(source_key('https://twitter.com/a/status/123/photo/2?s=1'),
                         source_key('https://x.com/b/status/123/video/1'))
        self.assertEqual(source_key('https://instagram.com/user/reel/AbC/?igsh=x'),
                         source_key('https://www.instagram.com/p/AbC/'))
        self.assertNotEqual(source_key('https://instagram.com/p/AbC/'), source_key('https://instagram.com/p/abc/'))
        self.assertEqual(source_key('https://threads.net/@a/post/AbC?x=1'), source_key('https://threads.com/@a/post/AbC'))

    def test_grouped_images_are_published_once_and_incremental_edits_preserve_text(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as patches:
            root = Path(temp)
            for name, value in {'DATA':str(root), 'CASES':str(root/'cases.json'),
                                'REJECTED':str(root/'rejected.json'), 'LOCK':str(root/'.lock'),
                                'MEDIA':str(root/'media')}.items():
                patches.enter_context(patch.object(store, name, value))
            library = root/'test.library'; library.mkdir()
            (library/'metadata.json').write_text('{}')
            def add(number):
                folder = library/'images'/f'{number}.info';folder.mkdir(parents=True)
                Image.new('RGB', (10, 10), (number*50, 0, 0)).save(folder/'sample.png')
                (folder/'metadata.json').write_text(json.dumps({'id':str(number),'ext':'png','name':'sample',
                    'url':'https://x.com/example/status/123/photo/'+str(number),'btime':number}))
            add(1);add(2)
            evidence = root/'evidence.txt';evidence.write_text('Original source evidence')
            group = {'sourceUrl':'https://x.com/example/status/123', 'eagleIds':['1','2'],
                     'evidence':[str(evidence)], 'fields':{'title':'Original title','description':'Verified description',
                     'category':'图标设计','tags':['图标'], 'source':{'author':'@example','url':'https://x.com/example/status/123'}}}
            state = root/'state.json'
            result = apply_manifest(scan(library), {'groups':[group]}, state)
            self.assertEqual(result[0]['status'], 'published')
            case = store.load_cases()[0]
            self.assertEqual(case['type'], 'graphic')
            self.assertEqual(len(case['media']['images']), 2)
            self.assertEqual(apply_manifest(scan(library), {'groups':[group]}, state)[0]['status'], 'skipped_existing')
            self.assertEqual(len(store.load_cases()), 1)
            edited = cms_content.change(case['id'], 'edit', {'title':'Human title','_version':case['_version']})
            edited = cms_content.change(case['id'], 'submit', {'_version':edited['_version']})
            cms_content.change(case['id'], 'approve', {'_version':edited['_version']})
            add(3);group['eagleIds'].append('3')
            self.assertEqual(apply_manifest(scan(library), {'groups':[group]}, state)[0]['status'], 'updated')
            case = store.load_cases()[0]
            self.assertEqual(case['title'], 'Human title')
            self.assertEqual(len(case['media']['images']), 3)
            self.assertEqual(len(store.load_cases()), 1)
            store.save_rejected([store.norm_url(group['sourceUrl'])])
            self.assertEqual(apply_manifest(scan(library), {'groups':[group]}, state)[0]['status'], 'skipped_rejected')

    def test_mixed_media_validation(self):
        value = {'media':{'kind':'images','items':[{'kind':'image','url':'/media/test/1.png'},
                {'kind':'video','url':'/media/test/2.mp4','thumbnail':'/media/test/cover.jpg'}]}}
        self.assertEqual(cms_content.validate(value), value)
        value['media']['items'][1]['url'] = 'javascript:alert(1)'
        with self.assertRaises(cms_content.ContentError):
            cms_content.validate(value)


if __name__ == '__main__':
    unittest.main()
