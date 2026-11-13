#!/usr/bin/env bash
set -Eeuo pipefail
sha="${1:?sha obrigatorio}"
acr_server="${2:?acr obrigatorio}"
kv="${3:?key vault obrigatorio}"
site="${4:?host obrigatorio}"
bundle="${5:?bundle obrigatorio}"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]]
root=/opt/vigia
umask 077
install -d -m 0750 "$root" "$root/deploy"
exec 9>"$root/deploy.lock"
flock -n 9
exec > >(tee -a /var/log/vigia-deploy.log) 2>&1
work=$(mktemp -d "$root/.deploy.XXXXXX")
previous="$root/previous"
active=0
trap 'rm -rf "$work"' EXIT

healthy() {
  local state
  for _ in $(seq 1 90); do
    state=$(cd "$root" && docker compose ps --format '{{.Health}}' app)
    if [[ "$state" == healthy ]]; then
      (cd "$root" && docker compose exec -T app python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3)") && return 0
    fi
    sleep 1
  done
  return 1
}

proxy_ready() {
  local host="${1:-$site}"
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 --resolve "$host:443:127.0.0.1" "https://$host/readyz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

rollback() {
  local old_sha
  if [[ -f "$previous/sha" ]]; then
    old_sha=$(<"$previous/sha")
    install -m 0640 "$previous/compose.yaml" "$root/compose.yaml"
    install -m 0640 "$previous/Caddyfile" "$root/deploy/Caddyfile"
    install -m 0600 "$previous/env" "$root/.env"
    if (cd "$root" && docker compose up -d --no-build --remove-orphans --pull never &&
        docker compose up -d --no-build --force-recreate --pull never caddy) && healthy &&
        proxy_ready "$(sed -n 's/^SITE_ADDRESS=//p' "$root/.env")"; then
      echo "DEPLOY_FALHOU $sha rollback para $old_sha"
    else
      echo "DEPLOY_FALHOU $sha rollback falhou para $old_sha"
    fi
  else
    (cd "$root" && docker compose down) || true
    echo "DEPLOY_FALHOU $sha sem versao anterior"
  fi
}
fail() {
  local status=$?
  trap - ERR
  if (( active )); then rollback; else echo "DEPLOY_FALHOU $sha antes da troca"; fi
  exit "$status"
}
trap fail ERR

az login --identity --allow-no-subscriptions --output none
az acr login --name "${acr_server%%.*}" >/dev/null
install -d -m 0750 "$work/bundle"
tar -xzf "$bundle" -C "$work/bundle"
for file in compose.yaml Caddyfile; do test -s "$work/bundle/$file"; done

pg=$(az keyvault secret show --vault-name "$kv" --name postgres-password --query value -o tsv)
hash=$(az keyvault secret show --vault-name "$kv" --name ip-hash-secret --query value -o tsv)
metrics=$(az keyvault secret show --vault-name "$kv" --name metrics-token --query value -o tsv)
{
  printf 'POSTGRES_PASSWORD=%s\nIP_HASH_SECRET=%s\nMETRICS_TOKEN=%s\n' "$pg" "$hash" "$metrics"
  printf 'SITE_ADDRESS=%s\nHTTP_PORT=80\nHTTPS_PORT=443\n' "$site"
  printf 'IMAGE_REPO=%s/vigia-chuva\nIMAGE_TAG=%s\n' "$acr_server" "$sha"
} > "$work/env"
unset pg hash metrics

if [[ -f "$root/tag_atual" ]]; then
  install -d -m 0700 "$previous"
  cp "$root/tag_atual" "$previous/sha"
  cp "$root/compose.yaml" "$previous/compose.yaml"
  cp "$root/deploy/Caddyfile" "$previous/Caddyfile"
  cp "$root/.env" "$previous/env"
fi
active=1
install -m 0640 "$work/bundle/compose.yaml" "$root/compose.yaml"
install -m 0640 "$work/bundle/Caddyfile" "$root/deploy/Caddyfile"
install -m 0600 "$work/env" "$root/.env"
(cd "$root" && docker compose config -q && docker compose pull)
# O erro de configuração não deve imprimir o cabeçalho com token.
if ! (cd "$root" && docker compose run --rm --no-deps caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile) >"$work/caddy-validacao.log" 2>&1; then
  echo "Configuracao do proxy recusada"
  false
fi
(cd "$root" && docker compose up -d --no-build --remove-orphans)
healthy
if [[ -f "$previous/Caddyfile" ]] && ! cmp -s "$previous/Caddyfile" "$root/deploy/Caddyfile"; then
  (cd "$root" && docker compose up -d --no-build --force-recreate caddy)
fi
proxy_ready
printf '%s\n' "$sha" > "$root/tag_atual"
echo "DEPLOY_OK $sha"
