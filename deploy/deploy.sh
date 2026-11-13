#!/usr/bin/env bash
set -Eeuo pipefail
sha="${1:?sha obrigatorio}"
acr_server="${2:?acr obrigatorio}"
kv="${3:?key vault obrigatorio}"
site="${4:?host obrigatorio}"
bundle="${5:?bundle obrigatorio}"
root=/opt/vigia
log=/var/log/vigia-deploy.log
umask 077
exec > >(tee -a "$log") 2>&1
work=$(mktemp -d "$root/.deploy.XXXXXX")
previous="$root/previous"
current="$root/current"
active=0
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
write_env() {
  local tag="$1" pg hash metrics
  pg=$(az keyvault secret show --vault-name "$kv" --name postgres-password --query value -o tsv)
  hash=$(az keyvault secret show --vault-name "$kv" --name ip-hash-secret --query value -o tsv)
  metrics=$(az keyvault secret show --vault-name "$kv" --name metrics-token --query value -o tsv)
  {
    printf 'POSTGRES_PASSWORD=%s\n' "$pg"
    printf 'IP_HASH_SECRET=%s\n' "$hash"
    printf 'METRICS_TOKEN=%s\n' "$metrics"
    printf 'SITE_ADDRESS=%s\nHTTP_PORT=80\nHTTPS_PORT=443\n' "$site"
    printf 'IMAGE_REPO=%s/vigia-chuva\nIMAGE_TAG=%s\n' "$acr_server" "$tag"
  } > "$root/.env"
  chmod 600 "$root/.env"
  unset pg hash metrics
}
rollback() {
  local old_sha
  if [[ -f "$previous/sha" ]]; then
    old_sha=$(<"$previous/sha")
    install -m 0640 "$previous/compose.yaml" "$root/compose.yaml"
    install -m 0640 "$previous/Caddyfile" "$root/deploy/Caddyfile"
    cp -a "$previous"/. "$current"/
    write_env "$old_sha"
    if (cd "$root" && docker compose pull && docker compose up -d --no-build --remove-orphans); then
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
  status=$?
  trap - ERR
  if (( active )); then rollback; else echo "DEPLOY_FALHOU $sha antes da troca"; fi
  exit "$status"
}
trap fail ERR
az login --identity --allow-no-subscriptions --output none
az acr login --name "${acr_server%%.*}" >/dev/null
install -d -m 0750 "$work/bundle" "$root/deploy"
tar -xzf "$bundle" -C "$work/bundle"
for file in compose.yaml Caddyfile; do test -s "$work/bundle/$file"; done
if [[ -f "$root/tag_atual" && -d "$current" ]]; then
  rm -rf "$previous"
  cp -a "$current" "$previous"
  cp "$root/tag_atual" "$previous/sha"
fi
cp -a "$work/bundle/." "$current/"
install -m 0640 "$current/compose.yaml" "$root/compose.yaml"
install -m 0640 "$current/Caddyfile" "$root/deploy/Caddyfile"
write_env "$sha"
active=1
(cd "$root" && docker compose pull && docker compose up -d --no-build --remove-orphans)
for _ in $(seq 1 90); do
  state=$(cd "$root" && docker compose ps --format '{{.Health}}' app)
  if [[ "$state" == healthy ]]; then
    printf '%s\n' "$sha" > "$root/tag_atual"
    printf '%s\n' "$sha" > "$current/sha"
    echo "DEPLOY_OK $sha"
    exit 0
  fi
  sleep 1
done
false
