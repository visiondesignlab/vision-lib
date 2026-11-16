"""External delivery must not change originals or re-export cached videos."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cms_content
import media_delivery
from scripts import sync_video_sources


class MediaDeliveryTests(unittest.TestCase):
    def test_local_only_source_is_not_added_to_public_catalog(self):
        case = {'id':'local', 'status':'published', 'notes':'Hold for review\n[local-only]',
                'source':{'url':'https://x.com/brand/status/456'},
                'media':{'kind':'video','video':'/media/local/web.mp4'}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = root/'catalog/video-sources.json'
            catalog.parent.mkdir()
            catalog.write_text('{"sources":{}}')
            with patch.object(sync_video_sources, 'ROOT', root), \
                    patch.object(sync_video_sources.store, 'load_cases', return_value=[case]), \
                    patch.object(sync_video_sources.xsource, 'resolve_post') as resolve:
                sync_video_sources.sync(refresh=True)
            resolve.assert_not_called()
            self.assertEqual(json.loads(catalog.read_text()), {'sources':{}})

    def test_public_source_keeps_private_original_intact(self):
        case = {'id':'sample', 'source':{'url':'https://x.com/brand/status/123'},
                'media':{'kind':'video','video':'/media/sample/web.mp4','preview':'/media/sample/preview.mp4',
                         'thumbnail':'/media/sample/thumb.jpg'}, 'notes':'private',
                'assets':[{'label':'原片','url':'/media/sample/web.mp4'}]}
        original = copy.deepcopy(case)
        with tempfile.TemporaryDirectory() as tmp, patch.object(media_delivery, 'ROOT', Path(tmp)):
            catalog = Path(tmp) / 'catalog/video-sources.json'
            catalog.parent.mkdir()
            catalog.write_text(json.dumps({'sources':{case['source']['url']:{'video':'https://video.twimg.com/sample.mp4'}}}))
            public = cms_content.public_view(case)
        self.assertEqual(case, original)
        self.assertNotIn('notes', public)
        self.assertEqual(public['media']['video'], 'https://video.twimg.com/sample.mp4')
        self.assertEqual(public['media']['thumbnail'], original['media']['thumbnail'])
        self.assertEqual(public['assets'][0]['url'], public['media']['video'])

    def test_new_online_sources_use_embed_until_resolved(self):
        case = {'source':{'url':'https://x.com/brand/status/456'},
                'media':{'kind':'video','video':'/media/new/web.mp4','preview':'/media/new/preview.mp4'}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(media_delivery, 'ROOT', Path(tmp)):
            media = cms_content.public_view(case)['media']
        self.assertEqual(media['embed'], 'remote')
        self.assertNotIn('video', media)
        self.assertNotIn('preview', media)

    def test_upload_without_online_source_remains_available(self):
        case = {'media':{'kind':'video','video':'/media/upload/web.mp4'}}
        self.assertEqual(cms_content.public_view(case), case)

    def test_provider_does_not_match_lookalike_hosts(self):
        for url in ('https://x.com.evil.test/brand/status/123','https://example.com/x.com/brand/status/123'):
            self.assertIsNone(media_delivery.provider(url))
