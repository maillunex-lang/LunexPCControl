#!/usr/bin/env python3
"""Portable, idempotent LunexPCControl VPS installer.

Default mode is a strictly read-only plan. --apply requires explicit intent.
No nginx, sshd, firewall or pre-existing services are reconfigured.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import secrets
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_DIR = pathlib.Path("/opt/lunexpc-gateway")
STATE_DIR = pathlib.Path("/var/lib/lunexpc-gateway")
LOG_DIR = pathlib.Path("/var/log/lunexpc-gateway")
SERVICE_NAME = "lunexpc-gateway.service"
ACCOUNT = "lunexpc-gateway"

FILES = {
    "server/gateway.py": APP_DIR / "server/gateway.py",
    "server/gateway_policy.py": APP_DIR / "server/gateway_policy.py",
    "server/screen_history.py": APP_DIR / "server/screen_history.py",
    "server/enrollment.py": APP_DIR / "server/enrollment.py",
    "server/sealed_token.py": APP_DIR / "server/sealed_token.py",
    "server/tunnel_config.py": APP_DIR / "server/tunnel_config.py",
    "deploy/verify-gateway.sh": APP_DIR / "deploy/verify-gateway.sh",
    "panel/server.py": APP_DIR / "panel/server.py",
    "panel/monitor_html.py": APP_DIR / "panel/monitor_html.py",
    "panel/auth.py": APP_DIR / "panel/auth.py",
    "installer/backup.py": APP_DIR / "installer/backup.py",
    "installer/install.py": APP_DIR / "installer/install.py",
    "installer/upgrade.py": APP_DIR / "installer/upgrade.py",
    "deploy/lunexpc-panel.service": pathlib.Path("/etc/systemd/system/lunexpc-panel.service"),
    "deploy/lunexpc-gateway.service": pathlib.Path("/etc/systemd/system/lunexpc-gateway.service"),
    "deploy/lunexpc-gateway.logrotate": pathlib.Path("/etc/logrotate.d/lunexpc-gateway"),
}

def validate_source():
    missing = [str(REPO_ROOT / name) for name in FILES if not (REPO_ROOT / name).is_file()]
    if missing:
        raise RuntimeError("incomplete GitHub source checkout: " + ", ".join(missing))
    if not (REPO_ROOT / "server/gateway.py").is_file():
        raise RuntimeError("missing server")
    for name, dst in FILES.items():
        if dst.is_symlink():
            raise RuntimeError(f"refusing symlink target: {dst}")
        if (REPO_ROOT / name).is_symlink():
            raise RuntimeError(f"refusing symlink source: {name}")


def command(*args):
    subprocess.run(list(args), check=True)


def is_existing_install() -> bool:
    return any(path.exists() for path in (
        pathlib.Path("/etc/systemd/system") / SERVICE_NAME,
        pathlib.Path("/etc/systemd/system/lunexpc-panel.service"),
        APP_DIR, STATE_DIR, LOG_DIR))


def plan():
    print("LunexPCControl VPS installer: READ-ONLY PLAN")
    print(f"Source checkout: {REPO_ROOT}")
    print(f"Target code: {APP_DIR}")
    print(f"State: {STATE_DIR} (private, preserved on upgrade)")
    print(f"Audit: {LOG_DIR} (private, preserved on upgrade)")
    print("Dedicated system user, two systemd units, logrotate: yes")
    print("Local read-only HTML dashboard: localhost:18881")
    print("Public nginx, firewall, sshd modifications: NEVER")
    print("Auto-start or public exposure: disabled")
    print(f"Existing deployment detected: {'yes' if is_existing_install() else 'no'}")


def check_host():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Linux VPS required")
    if pathlib.Path("/etc/os-release").exists():
        release = pathlib.Path("/etc/os-release").read_text()
        if not re.search(r'^ID=ubuntu$', release, flags=re.MULTILINE):
            raise RuntimeError("Ubuntu required")
    if sys.version_info < (3, 11):
        raise RuntimeError("Python >= 3.11 required")
    for binary in ("systemctl", "systemd-analyze", "useradd", "install", "runuser"):
        command("sh", "-c", f"command -v {binary} >/dev/null")
    command("/usr/bin/python3", "-c", "import cryptography")


def apply_install():
    if os.geteuid() != 0:
        raise PermissionError("--apply requires root")
    if is_existing_install():
        raise RuntimeError("existing installation: use a dedicated upgrade command later")
    for target in FILES.values():
        if target.exists():
            raise RuntimeError(f"target already exists: {target}")
    check_host()
    result = subprocess.run(["getent", "passwd", ACCOUNT], capture_output=True, text=True)
    if result.returncode == 0:
        fields = result.stdout.strip().split(":")
        if len(fields) != 7 or fields[5] != str(STATE_DIR) or fields[6] != "/usr/sbin/nologin":
            raise RuntimeError("existing system user conflicts with expected home/shell")
    else:
        command("useradd", "--system", "--user-group", "--home-dir",
                str(STATE_DIR), "--shell", "/usr/sbin/nologin", "--password", "!", ACCOUNT)
    command("install", "-d", "-m", "0755", "-o", "root", "-g", "root", str(APP_DIR), str(APP_DIR / "server"),
            str(APP_DIR / "deploy"), str(APP_DIR / "panel"))
    for folder in (STATE_DIR, LOG_DIR, STATE_DIR / "screens"):
        command("install", "-d", "-m", "0700", "-o", ACCOUNT, "-g", ACCOUNT, str(folder))
    for source_name, target in FILES.items():
        mode = "0755" if source_name.endswith(".sh") else "0644"
        command("install", "-m", mode, "-o", "root", "-g", "root",
                str(REPO_ROOT / source_name), str(target))
    init = ('from server.gateway import GatewayRegistry; '
            'GatewayRegistry("/var/lib/lunexpc-gateway/registry.sqlite")')
    command("runuser", "-u", ACCOUNT, "--", "sh", "-c",
            f'cd {APP_DIR} && /usr/bin/python3 -c \'{init}\'')
    panel_key_path = STATE_DIR / "panel-auth.key"
    if panel_key_path.exists() or panel_key_path.is_symlink():
        raise FileExistsError("panel credential file already exists")
    fd = os.open(panel_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, secrets.token_urlsafe(48).encode("ascii") + b"\n")
        os.fchown(fd, __import__("pwd").getpwnam(ACCOUNT).pw_uid,
                  __import__("grp").getgrnam(ACCOUNT).gr_gid)
    finally:
        os.close(fd)
    command("systemctl", "daemon-reload")
    command("systemd-analyze", "verify", f"/etc/systemd/system/{SERVICE_NAME}",
            "/etc/systemd/system/lunexpc-panel.service")
    print("Installed gateway and dashboard but intentionally not started or enabled.")
    print("Panel password was generated in private storage (never printed).")
    print("Retrieve it using your own authenticated VPS shell, not chat logs.")
    print("Next: verify settings and start manually with systemctl.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="install after review")
    args = parser.parse_args()
    validate_source()
    plan()
    if args.apply:
        apply_install()


if __name__ == "__main__":
    main()
