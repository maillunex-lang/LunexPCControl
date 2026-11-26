# Lunex Connector alpha: pairing a Windows or Linux device

1. Log in at https://rikagro.ru/portalmcp/devices.
2. Choose "Добавить Windows или Linux", select OS and a name, then
   create a single-use pairing code valid for 10 minutes.
3. Download the matching file from the published GitHub release and
   compare its SHA-256 digest against SHA256SUMS.txt.
4. On Windows, open PowerShell in the download folder, run
   .\lunex-connector-windows-amd64.exe pair
   and enter the code when prompted. For Linux, chmod +x the binary
   and run ./lunex-connector-linux-amd64 pair.
5. Start the presence connector with the same binary and the "run"
   argument. It sends HTTPS heartbeats and shows online after a valid
   signature is accepted.
6. To revoke, choose the device in the portal and click "Отозвать".
   The revoked device cannot resume heartbeat with its previous key.

For this alpha, the command must be launched manually. Per-user Windows
login tasks and systemd user units, update signing and packaging are
later steps, not claimed as shipped.

A paired alpha connector does NOT control the desktop, grant ChatGPT
access, expose files or open a network listener. Existing Windows
Screen Viewer and old SSH tunnels remain independently managed.

The identity stays in the user config directory, normally
%AppData%\LunexPCControl\connector.json on Windows and
~/.config/LunexPCControl/connector.json on Linux. It contains the
private Ed25519 signing key. Do not upload or share this file.

The connector requires HTTPS and refuses redirects to avoid exposing
the pairing code. Outbound Internet connectivity and accurate system
clock are required. It works across changes of the client's public IP.

The Windows/Linux executables are built from the public connector Go
source. Distribute them only with immutable release assets and checksums.
