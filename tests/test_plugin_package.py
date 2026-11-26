import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/"chatgpt-plugin"


class ChatGPTPluginPackageTests(unittest.TestCase):
    def test_manifest_and_authentication(self):
        plugin=json.loads((PKG/"plugin.json").read_text())
        server=json.loads((PKG/"mcp.json").read_text())
        self.assertEqual(plugin["name"],"lunexpc-control")
        self.assertEqual(plugin["version"],"0.1.0")
        self.assertEqual(plugin["$schema"],"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(server["$schema"],"https://agent-plugins.org/schemas/1.0.0/mcp.schema.json")
        config=server["mcpServers"]["lunexpc-readonly"]
        self.assertEqual(config["url"],"https://rikagro.ru/lunexpc-mcp")
        self.assertEqual(config["type"],"streamable-http")
        self.assertEqual(config["extensions"]["com.openai"]["auth"],
                         {"type":"api_key","headerScheme":"bearer"})
        self.assertLessEqual(len(plugin["extensions"]["com.openai"]["interface"]["shortDescription"]),30)

    def test_skills_mcp_metadata_and_no_secrets(self):
        skill=(PKG/"skills/remote-monitor/SKILL.md").read_text()
        self.assertTrue(skill.startswith("---\nname: remote-monitor\n"))
        self.assertIn("Screenshot",skill)
        self.assertIn("ControlStatus",skill)
        self.assertIn("NOT supported",skill)
        for rel in ("plugin.json","mcp.json","README.md","skills/remote-monitor/SKILL.md"):
            self.assertNotIn("PRIVATE KEY", (PKG/rel).read_text())


if __name__=="__main__":
    unittest.main()
