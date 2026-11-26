"""Generate a per-user Ed25519 tunnel identity and pin the VPS host key.

Run only under the intended interactive Windows user. No network services are
started. The private key is never copied out of the user-local directory.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import ipaddress
import os
import pathlib
import subprocess
import sys

EXPECTED_VPS = "195.216.188.80"
EXPECTED_HOST_FINGERPRINT = "SHA256:E4XxBUrI/KUjZLkJQA/zodQhr/20if9pZXpZd9ItM6k"


def fingerprint(ssh_base64: str) -> str:
    blob = base64.b64decode(ssh_base64, validate=True)
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def choose_host_key(scan: str, host: str, expected: str) -> str:
    matched = []
    for line in scan.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == host and parts[1] == "ssh-rsa":
            if fingerprint(parts[2]) == expected:
                matched.append(line)
    if not matched:
        raise ValueError("VPS host key fingerprint mismatch; refusing to pin untrusted host")
    return matched[0] + "\n"


def generate_identity(folder: pathlib.Path, comment: str) -> pathlib.Path:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = folder / "id_ed25519"
    pub = folder / "id_ed25519.pub"
    if priv.exists() != pub.exists():
        raise RuntimeError("Partial SSH key pair detected; refusing overwrite")
    if not priv.exists():
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption()
        )
        public = key.public_key().public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        with priv.open("xb") as stream:
            stream.write(private)
        os.chmod(priv, 0o600)
        with pub.open("xb") as stream:
            stream.write(public + b" " + comment.encode("ascii") + b"\n")
    else:
        from cryptography.hazmat.primitives.serialization import load_ssh_private_key
        key = load_ssh_private_key(priv.read_bytes(), password=None)
        expected_public = key.public_key().public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        if not pub.read_bytes().startswith(expected_public + b" "):
            raise RuntimeError("Existing public key does not match private key")
    return pub


def provision(folder: pathlib.Path, public_export: pathlib.Path,
              host: str = EXPECTED_VPS,
              expected: str = EXPECTED_HOST_FINGERPRINT,
              ssh_keyscan: str = "ssh-keyscan") -> str:
    ipaddress.ip_address(host)
    folder.mkdir(parents=True, exist_ok=True)
    # Do not derive secret material from weak PRNGs or reveal key to stdout.
    pub = generate_identity(folder, "lunexpc-device")
    scan = subprocess.run(
        [ssh_keyscan, "-T", "8", "-t", "rsa", host],
        text=True, capture_output=True, timeout=22, check=False
    )
    host_line = choose_host_key(scan.stdout, host, expected)
    known_hosts = folder / "known_hosts"
    if known_hosts.exists():
        if known_hosts.read_text(encoding="ascii") != host_line:
            raise RuntimeError("Pinned host key changed; refusing overwrite")
    else:
        with known_hosts.open("x", encoding="ascii") as stream:
            stream.write(host_line)
    public = pub.read_text(encoding="ascii")
    if public_export.exists():
        if public_export.read_text(encoding="ascii") != public:
            raise RuntimeError("Public export already contains a different key")
    else:
        with public_export.open("x", encoding="ascii") as stream:
            stream.write(public)
    return fingerprint(host_line.split()[2])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=pathlib.Path, required=True)
    parser.add_argument("--public-export", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        fp = provision(args.folder, args.public_export)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"SSH identity provisioning failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"SSH identity ready; VPS pinned fingerprint: {fp}; private key NOT exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
