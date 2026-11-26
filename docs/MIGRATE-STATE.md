# Portable encrypted LunexPCControl state migration (v2)

**Source files and the releases are public on GitHub. Private device state is
not and must never be committed.** This document covers transferring encrypted
state between owner-controlled Ubuntu VPS hosts. The operation is intentionally
separate from fresh installation and does not depend on Termalin.

## State included in v2

The v2 encrypted archive includes only known files, when present:

- Required: MCP gateway SQLite registry (registry.sqlite) and the private
  panel authentication credential (panel-auth.key).
- Optional: paired-connector registry database, screenshot-history database,
  screenshot AES-256 key and retained encrypted .enc screenshot files.
- Optional: private Linux Lunex Connector Ed25519 identity, private gateway
  *.key files, existing encrypted-backup key and the restricted SSH
  authorized_keys list used by the outbound Windows tunnel.

Live SQLite files are copied with the SQLite online backup API to an in-memory
snapshot, not by copying an inconsistent database file. Other files must be
private regular files, never symlinks. Source files have strict size limits.
The archive uses AES-256-GCM and file SHA-256 integrity checks.

**Not included:** Windows-side SSH private keys or Windows Credential Manager
state, Windows FFmpeg installation, TLS private keys managed by an external
certificate provider, DNS records, unrelated game services, server SSH host
private keys or other unknown application files. These require separate
migration. A changed VPS SSH host key requires the owner to explicitly
review and update Windows-side pinning.

## Create and verify on the old VPS

Use a full source checkout and run as an administrator. A separate
32-byte encryption key file with permissions 0600 must already exist.
Generate one when needed using:

    python3 installer/backup.py keygen --output /private/backup.key

Store the key separately from the encrypted archive and outside the VPS in
secure owner-controlled storage. Without the key, the archive cannot be
recovered.

Example with the current dedicated private key and backup folder:

    cd /path/to/LunexPCControl
    sudo install -d -m 0700 /var/backups/lunexpc
    sudo python3 -m installer.migration create \
      --source-root / \
      --key-file /etc/lunexpc-gateway/backup.key \
      --output /var/backups/lunexpc/state-EXAMPLE.enc
    sudo python3 -m installer.migration verify \
      --backup /var/backups/lunexpc/state-EXAMPLE.enc \
      --key-file /etc/lunexpc-gateway/backup.key

Choose a unique archive name; the command refuses to replace an existing
backup. Do not paste the key, archive contents, device credentials or
screenshot data into ChatGPT, tickets, shell history or public GitHub.
The backup has mode 0600; the parent folder should be 0700.
Transfer the encrypted archive and its key by separate secure channels.

## Verify and stage on the new VPS

First make a clean installation from the exact reviewed Git commit. Prepare
the encryption key as an independent private file 0600, then:

    cd /path/to/LunexPCControl
    sudo python3 -m installer.migration verify \
      --backup /private/state-EXAMPLE.enc \
      --key-file /private/owner-exported.key
    sudo python3 -m installer.migration stage \
      --backup /private/state-EXAMPLE.enc \
      --key-file /private/owner-exported.key \
      --output /root/lunexpc-private-restore-stage

**The stage command never modifies /var/lib, systemd, nginx or SSH.**
It creates an entirely new 0700 directory and private 0600 files for review.
It refuses to use an existing stage destination; path traversal, unknown
files, corrupted archives and duplicate paths are rejected.
At this milestone, applying the extracted state with service stop,
ownership mapping, backup and rollback remains a separate manual operation.
Never copy staged files over a running database.

The legacy installer/backup.py v1 format, containing only the gateway
registry and panel credential, remains unchanged. V2 is a separate
encrypted envelope.

## Portability and release status

The source checkout can be downloaded on another VPS; the installed
application layout has automated isolated smoke tests. **A fresh production
installation, full migration activation, Linux/Windows re-enrollment, Nginx
HTTPS configuration and video/MCP end-to-end validation on a second VPS are
not yet verified.** Do not treat this encrypted archive as a complete one-click
restore or as a guarantee that all external dependencies survive migration.
