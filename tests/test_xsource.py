import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mediautil
import server
import xsource


class XSourceTests(unittest.TestCase):
    def test_video_quality_matches_original_in_multi_video_post(self):
        prefix = "https://video.twimg.com/amplify_video/"
        variants = [{"url": prefix + path, "bitrate": rate} for path, rate in [
            ("wrong/vid/1920x1080/a.mp4", 9000),
            ("right/vid/3840x2160/b.mp4", 8000),
            ("right/vid/1280x720/c.mp4", 2000),
            ("right/vid/1920x1080/d.mp4", 4000)]]
        urls = xsource.video_urls({"variants": variants}, prefix + "right/vid/3840x2160/b.mp4")
        self.assertEqual(urls[0], prefix + "right/vid/1920x1080/d.mp4")
        self.assertFalse(any("/wrong/" in url for url in urls))

    def test_enrichment_preserves_review_and_separates_discovery(self):
        case = {"id": "example", "status": "pending", "title": "Product", "media": {},
                "tags": ["AI", "launchvideos.gallery"], "source": {"url": "https://x.com/original/status/123",
                "via": "launchvideos.gallery", "via_url": "https://launchvideos.gallery/videos/example",
                "author": "@brand", "metrics": {"views": 900}, "metrics_fetched_at": "old"}}
        original = copy.deepcopy(case)
        metadata = {"author": "original", "avatar": "https://pbs.twimg.com/profile_images/1/a.jpg",
                    "metrics": {"likes": 20, "views": None}, "fetched_at": "2026-11-04"}
        with patch.object(xsource, "cache_avatar", return_value="/media/avatars/a.jpg"), \
             patch.object(xsource, "cache_video", return_value={"video": "/media/example/web.mp4", "preview": "/media/example/preview.mp4"}):
            result, errors = xsource.enrich(case, metadata)
        self.assertEqual(case, original)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["source"]["author"], "@original")
        self.assertEqual(result["source"]["metrics"], {"likes": 20})
        self.assertEqual(result["tags"], ["AI"])
        self.assertEqual(result["discovery"]["reported_metrics"], {"views": 900})
        self.assertNotIn("discovery", server.public_view(result))
        self.assertNotIn("via", result["source"])
        self.assertFalse(errors)

    def test_failed_conversion_does_not_publish_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, "web.mp4")
            def fail(args):
                Path(args[-1]).write_bytes(b"partial output")
                raise RuntimeError("Conversion interrupted")
            with patch.object(mediautil, "_ff", side_effect=fail):
                with self.assertRaises(RuntimeError):
                    mediautil._ff_atomic(["-i", "source.mp4", target])
            self.assertFalse(os.path.exists(target))
            self.assertEqual(os.listdir(folder), [])

    def test_missing_avatar_has_no_fabricated_fallback(self):
        self.assertEqual(xsource.cache_avatar(""), "")
        self.assertEqual(xsource.cache_avatar("https://example.com/logo.jpg"), "")

    def test_post_parser_rejects_lookalike_domains(self):
        self.assertEqual(xsource.post_id("https://x.com/user/status/123"), "123")
        self.assertIsNone(xsource.post_id("https://notx.com/user/status/123"))


if __name__ == "__main__":
    unittest.main()
