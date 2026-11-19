#!/usr/bin/env python3
"""End-to-end test of libexec/check_file_hash against a local http.server.

Run:  python3 tests/test_check_file_hash.py   (stdlib only)
"""

import functools
import hashlib
import http.server
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "src/file_hash/libexec/check_file_hash"
CONTENT = b"Hallo Checkmk!\n" * 100_000  # ~1.5 MB, streamed in chunks


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


class CheckFileHashTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        Path(cls.tmp.name, "file.bin").write_bytes(CONTENT)
        handler = functools.partial(_QuietHandler, directory=cls.tmp.name)
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def run_check(self, *args):
        proc = subprocess.run([str(CHECK), *args], capture_output=True, text=True, timeout=30)
        print(f"  [{proc.returncode}] {proc.stdout.strip()}")
        return proc.returncode, proc.stdout

    def test_match_all_algorithms_case_insensitive(self):
        for algo in ("md5", "sha1", "sha256", "sha512"):
            digest = hashlib.new(algo, CONTENT).hexdigest().upper()
            rc, out = self.run_check("--url", f"{self.base}/file.bin",
                                     "--algorithm", algo, "--expected", digest)
            self.assertEqual(rc, 0, out)
            self.assertIn(f"size={len(CONTENT)}B", out)
            self.assertIn("duration=", out)

    def test_default_algorithm_is_sha256(self):
        rc, out = self.run_check("--url", f"{self.base}/file.bin",
                                 "--expected", hashlib.sha256(CONTENT).hexdigest())
        self.assertEqual(rc, 0, out)

    def test_mismatch(self):
        wrong = "0" * 64
        rc, out = self.run_check("--url", f"{self.base}/file.bin", "--expected", wrong)
        self.assertEqual(rc, 2, out)
        self.assertIn("MISMATCH", out)
        self.assertIn(wrong, out)
        self.assertIn(hashlib.sha256(CONTENT).hexdigest(), out)

    def test_http_404(self):
        rc, out = self.run_check("--url", f"{self.base}/missing.bin", "--expected", "0" * 64)
        self.assertEqual(rc, 2, out)
        self.assertIn("HTTP 404", out)

    def test_connection_refused(self):
        rc, out = self.run_check("--url", "http://127.0.0.1:1/x", "--expected", "0" * 64,
                                 "--timeout", "3")
        self.assertEqual(rc, 2, out)

    def test_bad_arguments(self):
        for args in ([], ["--url", f"{self.base}/file.bin"],
                     ["--url", "ftp://x/y", "--expected", "0" * 64],
                     ["--url", f"{self.base}/file.bin", "--expected", "abc"],
                     ["--url", f"{self.base}/file.bin", "--algorithm", "crc32",
                      "--expected", "0" * 8]):
            rc, out = self.run_check(*args)
            self.assertEqual(rc, 3, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
