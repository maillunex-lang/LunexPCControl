import unittest
from panel.portal_html import devices_page


class ConnectorUITests(unittest.TestCase):
    def test_owner_pairing_and_revocation_controls_present(self):
        html=devices_page().decode("utf-8")
        for part in (
            'id="createInvite"', 'id="newOs"', 'id="newName"',
            'id="pairCode"', 'id="managedDevices"',
            '/portalmcp/api/connectors/invitations',
            '/portalmcp/api/connectors/revoke',
            '/portalmcp/api/connectors',
            'X-LunexPC-Action',
            'connector-revoke',
            'connector-invite',
            'textContent=data.pairing_code',
            'v0.3.0-connector-alpha.1',
            'SHA256SUMS.txt',
            'id="downloadConnector"',
            'confirm(',
            'Мой компьютер',
        ):
            self.assertIn(part,html)
        self.assertNotIn("localStorage",html)
        self.assertNotIn("sessionStorage",html)
        self.assertNotIn("innerHTML=",html)
        self.assertNotIn("http://127.0.0.1:23790",html)

    def test_not_claim_full_remote_input_access(self):
        html=devices_page().decode()
        self.assertIn("не даёт ИИ доступ к мыши",html)
        self.assertIn("Права доступа выдаются отдельно",html)


if __name__=="__main__":
    unittest.main()
