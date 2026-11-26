#!/usr/bin/env bash
# Pinned one-command Ubuntu installer. Safe plan mode by default.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
REPO="https://github.com/maillunex-lang/LunexPCControl.git"
REF=""
APPLY=0
usage() {
  echo "Usage: bootstrap.sh --ref FULL_40_CHARACTER_COMMIT_SHA [--apply]"
  echo "Without --apply, installation plan only."
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ref)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      REF="$2"
      shift 2
      ;;
    --apply) APPLY=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
if [[ ! "$REF" =~ ^[a-fA-F0-9]{40}$ ]]; then
  echo "ERROR: an immutable full 40-character Git revision is required" >&2
  exit 2
fi
if [ "$APPLY" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: --apply requires sudo/root" >&2
  exit 2
fi
for command_name in git python3 mktemp; do
  command -v "$command_name" >/dev/null || {
    echo "ERROR: missing prerequisite: $command_name" >&2
    exit 2
  }
done
if [ "$APPLY" -eq 1 ] && [ -e /etc/systemd/system/lunexpc-gateway.service ]; then
  echo "ERROR: existing installation, refusing overwrite" >&2
  exit 2
fi
TEMP="$(mktemp -d -t lunexpc-bootstrap-XXXXXXXX)"
trap 'rm -rf -- "$TEMP"' EXIT
git clone --quiet "$REPO" "$TEMP/source"
git -C "$TEMP/source" checkout --quiet --detach "$REF"
FOUND="$(git -C "$TEMP/source" rev-parse HEAD)"
if [ "$FOUND" != "$REF" ]; then
  echo "ERROR: downloaded Git revision mismatch" >&2
  exit 1
fi
echo "Verified source revision: $FOUND"
if [ "$APPLY" -eq 1 ]; then
  python3 "$TEMP/source/installer/install.py" --apply
else
  python3 "$TEMP/source/installer/install.py"
fi
echo "Complete. No service or public access is automatically enabled."
