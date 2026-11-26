#!/usr/bin/env python3
"""Verify and stage an immutable LunexPCControl update without activating it.

Does NOT restart services, overwrite the existing installation or alter state.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from installer.install import FILES, REPO_ROOT

DEFAULT_STAGES = Path("/opt/lunexpc-gateway-updates")


def git_read(*args):
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), *args], text=True).strip()


def verify_checkout(revision):
    if not re.fullmatch(r"[0-9a-f]{40}",revision):
        raise ValueError("full lowercase 40-character Git commit required")
    if git_read("rev-parse", "HEAD") != revision:
        raise ValueError("checkout does not match requested revision")
    if git_read("status","--porcelain"):
        raise ValueError("source checkout has uncommitted changes")
    for rel in FILES:
        source = REPO_ROOT / rel
        if not source.is_file() or source.is_symlink():
            raise ValueError("missing or symlink source: " + rel)


def build_manifest(source_root=REPO_ROOT):
    manifest = {}
    total = 0
    for rel in FILES:
        file = source_root / rel
        contents = file.read_bytes()
        total += len(contents)
        if total > 2 * 1024 * 1024:
            raise ValueError("unexpected update source size")
        manifest[rel] = hashlib.sha256(contents).hexdigest()
    return manifest


def stage(revision, parent=DEFAULT_STAGES):
    verify_checkout(revision)
    if os.geteuid() != 0:
        raise PermissionError("update staging requires root")
    parent = Path(parent)
    if parent.is_symlink():
        raise ValueError("staging directory may not be a symlink")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(parent,0o700)
    destination = parent / revision
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("staged update already exists")
    destination.mkdir(mode=0o700)
    manifest = build_manifest()
    try:
        for name in manifest:
            source = REPO_ROOT / name
            target = destination / name
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with target.open("xb") as out:
                out.write(source.read_bytes())
            target.chmod(0o600)
        (destination/"manifest.json").write_text(
            json.dumps({"commit":revision,"files":manifest},indent=2)+"\n")
        (destination/"manifest.json").chmod(0o600)
        check_stage(destination)
    except Exception:
        # Remove only the newly created staging directory, never a live install.
        shutil.rmtree(destination)
        raise
    return destination


def check_stage(destination):
    destination=Path(destination)
    if destination.is_symlink():
        raise ValueError("invalid staged directory")
    record=destination/"manifest.json"
    if record.is_symlink():
        raise ValueError("invalid manifest")
    doc=json.loads(record.read_bytes())
    commit=doc.get("commit")
    if not isinstance(commit,str) or not re.fullmatch(r"[0-9a-f]{40}",commit):
        raise ValueError("invalid staged revision")
    if not isinstance(doc.get("files"),dict) or set(doc["files"]) != set(FILES):
        raise ValueError("invalid staged file inventory")
    for name,digest in doc["files"].items():
        file=destination/name
        if not file.is_file() or file.is_symlink():
            raise ValueError("missing staged file: "+name)
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError("staged file integrity mismatch: "+name)
    return {"revision":commit, "files":len(doc["files"])}


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--ref",help="full immutable Git commit SHA")
    cli.add_argument("--stage",action="store_true",
                     help="copy a verified revision to private staging; no activation")
    cli.add_argument("--check-stage",type=Path,
                     help="verify already staged files without changing anything")
    args=cli.parse_args()
    if args.check_stage:
        status=check_stage(args.check_stage)
        print("Staged update verified:",status["revision"],status["files"],"files")
        return
    if not args.ref:
        raise ValueError("--ref is required")
    if args.stage:
        path=stage(args.ref)
        print("Update safely staged at",path)
        print("Activation not supported yet: backup and rollback gate pending")
    else:
        verify_checkout(args.ref)
        print("Update plan validated:",args.ref)
        print("Only staging is implemented. No service will be restarted.")


if __name__=="__main__":
    main()
