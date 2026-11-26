import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ConnectorServiceTests(unittest.TestCase):
    def test_service_is_unprivileged_and_outbound_only(self):
        unit=(ROOT/"deploy/lunexpc-connector.service").read_text()
        for expected in (
            "User=lunexpc-agent",
            "Group=lunexpc-agent",
            "ExecStart=/opt/lunexpc-connector/lunex-connector run",
            "ProtectSystem=strict",
            "ReadWritePaths=/var/lib/lunexpc-agent",
            "NoNewPrivileges=yes",
            "CapabilityBoundingSet=",
            "MemoryMax=64M",
            "PrivateDevices=yes",
        ):
            self.assertIn(expected,unit)
        for forbidden in ("User=root","0.0.0.0","/var/lib/lunexpc-gateway",
                          "ExecStartPre=/bin/sh","ExecStart=/bin/bash",
                          "AmbientCapabilities=CAP_"):
            self.assertNotIn(forbidden,unit)
    def test_docs_distinguish_presence_from_remote_control(self):
        text=(ROOT/"docs/CONNECTOR-VPS-SERVICE.md").read_text()
        self.assertIn("signed online presence",text)
        self.assertIn("revocation",text)
        self.assertIn("private identity",text)
