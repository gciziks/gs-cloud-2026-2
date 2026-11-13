#!/usr/bin/env bash
set -euo pipefail

acao="${1:-}"
case "$acao" in
  parar) comando='cd /opt/vigia && docker compose stop app && echo DEMO_ALERTA_APP_PARADA' ;;
  voltar) comando='cd /opt/vigia && docker compose start app && echo DEMO_ALERTA_APP_ATIVA' ;;
  *) printf 'Uso: %s parar|voltar\n' "$0" >&2; exit 2 ;;
esac

: "${RG_NOME:?defina RG_NOME}"
: "${VM_NOME:?defina VM_NOME}"

marcador="${comando##*echo }"
saida="$(az vm run-command invoke \
  --resource-group "$RG_NOME" \
  --name "$VM_NOME" \
  --command-id RunShellScript \
  --scripts "$comando" \
  --query 'value[].message' -o tsv)"

if [[ "$saida" != *"$marcador"* ]]; then
  printf 'Run-command não confirmou a ação (%s).\n' "$marcador" >&2
  exit 1
fi
printf 'Ação remota confirmada: %s\n' "$marcador"
