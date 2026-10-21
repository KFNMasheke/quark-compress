"""Exercise the real local API and bounded untrusted restoration boundary."""
import gzip
import http.client
import json
import lzma
import threading
import time
import unittest
import zstandard as zstd
from quarkcompress import core, qcore
from quarkcompress.gui import create_server, restore

class RestoreTests(unittest.TestCase):
    def test_supported_formats_round_trip(self):
        original = b'GUI round trip\x00' * 300
        for codec in core.CODECS:
            if codec == 'store':
                continue
            with self.subTest(codec=codec):
                self.assertEqual(restore(core.encode(original, codec)), original)

    def test_extra_frames_and_bombs_rejected(self):
        for encode in (gzip.compress, lzma.compress, zstd.ZstdCompressor().compress):
            with self.subTest(engine=encode):
                packed = encode(b'x')
                with self.assertRaises(Exception):
                    restore(packed + packed)
                with self.assertRaises(Exception):
                    restore(encode(b'x' * (core.MAX_INPUT + 1)))
        with self.assertRaises(ValueError):
            restore(b'not an archive')

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f'127.0.0.1:{self.server.server_port}'
        self.token = self.request('GET', '/api/session')[1]['token']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, url, body=None, headers=None, raw=False):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        conn.request(method, url, body, headers or {})
        response = conn.getresponse()
        data = response.read()
        result = (response.status, data if raw else json.loads(data))
        conn.close()
        return result

    def test_host_and_mutation_protection(self):
        self.assertEqual(self.request('GET', '/api/session', headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('POST','/api/jobs',b'x')[0],403)
        self.assertEqual(self.request('POST','/api/jobs',b'x',{'Origin':'https://evil.example','X-Quark-Token':self.token})[0],403)
        self.assertEqual(self.request('GET','/../../pyproject.toml')[0],404)

    def test_upload_verify_download_and_restore(self):
        original=b'hello graphical workspace\n'*100
        headers={'Origin':'http://'+self.host,'X-Quark-Token':self.token}
        status,created=self.request('POST','/api/jobs?name=test.txt&codec=zstd-3',original,headers)
        self.assertEqual(status,202)
        for _ in range(100):
            job=self.request('GET','/api/jobs/'+created['id'])[1]
            if job['status']!='running':break
            time.sleep(.01)
        self.assertEqual(job['status'],'complete')
        self.assertTrue(job['verified'])
        code,packed=self.request('GET','/api/jobs/'+created['id']+'/download',raw=True)
        self.assertEqual(code,200)
        self.assertEqual(restore(packed),original)
