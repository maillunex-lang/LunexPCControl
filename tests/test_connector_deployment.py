import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ConnectorDeploymentTests(unittest.TestCase):
    def test_service_sandbox_restricts_writes_to_specific_folders(self):
        unit=(ROOT/"deploy/lunexpc-panel.service").read_text()
        self.assertIn("ProtectSystem=strict",unit)
        self.assertIn("ReadWritePaths=/var/lib/lunexpc-gateway/screens /var/lib/lunexpc-gateway/connectors",unit)
        self.assertNotIn("ReadWritePaths=/var/lib/lunexpc-gateway\\n",unit)
        self.assertIn('"/var/lib/lunexpc-gateway/connectors/registry.sqlite"',
                      (ROOT/"panel/server.py").read_text())
        self.assertIn('STATE_DIR / "connectors"',(ROOT/"installer/install.py").read_text())
