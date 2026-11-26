# Optional Lunex Connector Linux systemd service

The optional connector service provides only signed online presence.
It runs as the dedicated unprivileged lunexpc-agent system user, with
its private Ed25519 key in /var/lib/lunexpc-agent/LunexPCControl/connector.json.
No shell, file, desktop, root permission or inbound network port is granted.

The executable is compiled from connector/ and installed at
/opt/lunexpc-connector/lunex-connector after checking the GitHub
release SHA-256 manifest. The owner creates an ordinary 10-minute
Linux pairing invitation in https://rikagro.ru/portalmcp/devices;
the code is entered locally and never added to a command line or URL.
The backend stores only the public key. The service is not required
on the same VPS as the portal; any Ubuntu or Linux machine can enroll.

To stop a service immediately:
    sudo systemctl stop lunexpc-connector

To prevent it from starting after reboot:
    sudo systemctl disable lunexpc-connector

To check:
    sudo systemctl status lunexpc-connector
    sudo journalctl -u lunexpc-connector -n 30 --no-pager

Device revocation in the portal rejects all future signed heartbeats.
Stopping the Linux service and revoking the device are separate actions.
The agent stores its local private identity and does not auto-delete
it when the owner revokes the connection; this avoids unintended data loss.
Do not share the private identity file or print it in logs.

This optional service never changes sshd, firewall, Termalin, nginx,
Windows-MCP or game services. Its presence status is not evidence that
remote desktop permissions have been granted.
