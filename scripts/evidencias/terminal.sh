#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'Uso: %s <arquivo.png> <comando> [argumentos...]\n' "$0" >&2
  exit 2
fi

destino="$1"
shift
comando="$*"
mkdir -p "$(dirname "$destino")"

node "$(dirname "$0")/terminal-capture.mjs" "$destino" "$comando"
