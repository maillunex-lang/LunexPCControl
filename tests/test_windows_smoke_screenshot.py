import base64
import importlib.util
import pathlib
import types
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "agent/windows/smoke_screenshot.py"
spec = importlib.util.spec_from_file_location("screenshot_smoke", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SmokeScreenshotTests(unittest.TestCase):
    def test_only_loopback_mcp(self):
        self.assertEqual(
            mod.validate_endpoint("http://127.0.0.1:18789/mcp"),
            "http://127.0.0.1:18789/mcp",
        )
        for endpoint in (
            "http://localhost:18789/mcp", "http://example.com/mcp",
            "http://127.0.0.1:1/mcp", "https://127.0.0.1:18789/mcp",
            "http://127.0.0.1:18789/admin", "http://127.0.0.1:18789/mcp?q=1",
            "http://user:secret@127.0.0.1:18789/mcp",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                mod.validate_endpoint(endpoint)

    def test_png_content(self):
        data = base64.b64encode(mod.PNG_SIGNATURE + b"test").decode()
        result = types.SimpleNamespace(
            isError=False,
            content=[types.SimpleNamespace(type="image", data=data)],
        )
        self.assertEqual(mod.summarize_screenshot(result), {"images": 1, "bytes": 12})

    def test_no_image_or_bad_image(self):
        for content in (
            [], [types.SimpleNamespace(type="text", text="error")],
            [types.SimpleNamespace(type="image", data="!!!")],
            [types.SimpleNamespace(type="image", data=base64.b64encode(b"jpeg").decode())],
        ):
            with self.assertRaises(ValueError):
                mod.summarize_screenshot(types.SimpleNamespace(content=content))

    def test_mcp_error(self):
        with self.assertRaises(ValueError):
            mod.summarize_screenshot(types.SimpleNamespace(isError=True, content=[]))
