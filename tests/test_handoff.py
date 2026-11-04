"""Read-only checks: retired online analysis endpoints never start work."""
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class QuietHandler(server.H):
    def log_message(self, *args):
        pass


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def test_retired_endpoint_never_reads_cases_or_starts_analysis(self):
        with patch.object(server.store, "load_cases", side_effect=AssertionError("Unexpected case access")):
            for method in ("GET", "POST", "PUT"):
                for suffix in ("", "/"):
                    with self.subTest(method=method, suffix=suffix):
                        request = Request(self.base + "/api/cases/example/breakdown" + suffix,
                                          data=b'{"force":true}' if method != "GET" else None,
                                          method=method, headers={"Content-Type": "application/json"})
                        with self.assertRaises(HTTPError) as response:
                            urlopen(request, timeout=5)
                        self.assertEqual(response.exception.code, 410)
                        with response.exception as error:
                            self.assertEqual(json.load(error)["code"], "online_breakdown_removed")
        self.assertNotIn("breakdown", sys.modules)

    def test_normal_case_endpoint_still_works(self):
        case = {"id": "example", "status": "published", "title": "Example"}
        with patch.object(server.store, "load_cases", return_value=[case]):
            with urlopen(self.base + "/api/cases/example", timeout=5) as response:
                self.assertEqual(json.load(response), case)


if __name__ == "__main__":
    unittest.main()
