#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$HOME/.config/trainfo.env"

if [[ ! -f "$ENV_FILE" ]]; then
  print -u2 "Missing $ENV_FILE"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/download_trainfo.py"