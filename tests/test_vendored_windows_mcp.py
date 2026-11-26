import hashlib,json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class VendoredWindowsMcpTests(unittest.TestCase):
    def test_complete_pinned_source(self):
        manifest=json.loads((ROOT/'vendor/WINDOWS-MCP-SHA256.json').read_text())
        self.assertEqual(manifest['commit'],
                         (ROOT/'vendor/WINDOWS-MCP-COMMIT.txt').read_text().strip())
        self.assertEqual(manifest['license'],'MIT')
        self.assertGreaterEqual(len(manifest['files']),240)
        for name,digest in manifest['files'].items():
            with self.subTest(path=name):
                file=ROOT/'vendor/windows-mcp'/name
                self.assertTrue(file.is_file())
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),digest)
        self.assertTrue((ROOT/'vendor/windows-mcp/LICENSE.md')
                        .read_text().startswith('MIT License'))
