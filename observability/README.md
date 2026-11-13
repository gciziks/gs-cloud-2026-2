# Observabilidade

Prometheus e Grafana rodam localmente. As portas 9090 e 3000 ficam limitadas a `127.0.0.1`; dashboards e regras ficam em arquivos versionados e os dados persistem nos volumes Docker `prometheus_data` e `grafana_data`.

## Preparar

```bash
cd observability
cp .env.example .env
mkdir -p .segredos
```

Defina `MVP_HOST` como o FQDN da VM, sem esquema. Use `MVP_SCHEME=https`. Gere `NTFY_TOPICO` com `python -c "import secrets; print('vigia-chuva-' + secrets.token_hex(12))"` e `GRAFANA_ADMIN_PASSWORD` com `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Guarde o tópico e a senha no `.env`, sem colocá-los em comandos que possam ficar no histórico.

O token de métricas vem do Key Vault. Execute localmente e sem `-v` para gravar somente o valor em arquivo:

```bash
az keyvault secret show --vault-name <kv> --name metrics-token --query value -o tsv > .segredos/metrics_token
chmod 600 .segredos/metrics_token
```

O `.env` e `.segredos/` são ignorados pelo Git. Não use `cat`, `echo`, `set -x` ou captura de terminal ao lidar com esses valores.

## Iniciar e conferir

```bash
docker compose up -d
curl -fsS http://127.0.0.1:9090/api/v1/targets
```

Os dois alvos devem aparecer `up` quando a VM estiver acessível e o token tiver sido carregado corretamente. Grafana: `http://127.0.0.1:3000`, usuário `admin`. Para a stack local do MVP, ajuste `MVP_HOST=host.docker.internal:8080` e `MVP_SCHEME=http`.

Após editar arquivos de provisionamento, aplique com `docker compose restart grafana prometheus`. Para conferir os recursos pelo API:

```bash
curl -fsS 'http://127.0.0.1:3000/api/search?query=sinais' -u admin
curl -fsS http://127.0.0.1:3000/api/v1/provisioning/alert-rules -u admin
curl -fsS http://127.0.0.1:3000/api/v1/provisioning/contact-points -u admin
```

O `curl -u admin` solicita a senha de forma interativa. O dashboard é `vigia-sinais`; as regras ficam na pasta `Vigia`.

## Carga e demonstração de alerta

Use carga somente contra um MVP acessível e com autorização. Não envie POST de relatos.

```bash
docker compose --profile carga run --rm -e MVP_URL=https://<MVP_HOST> k6 run /scripts/carga.js
```

Para provocar o alerta remoto, defina `RG_NOME` e `VM_NOME` no ambiente local e chame `scripts/demo-alerta.sh parar`. O script só confirma sucesso se o texto de saída do run-command contiver o marcador da ação. Depois de observar o alerta em firing, chame `scripts/demo-alerta.sh voltar` e aguarde a resolução. Isso para e inicia apenas o serviço `app` da VM.

Com `NTFY_TOPICO` vazio, o contact point fica provisionado sem destino útil e não envia notificações. Com tópico preenchido, o Grafana publica em `https://ntfy.sh/<tópico>` usando o modelo Grafana.

## Capturas

Instale as dependências e o Chromium uma vez na raiz:

```bash
npm ci
npx playwright install chromium
```

Captura de uma página genérica:

```bash
node scripts/evidencias/web.mjs https://<url> scripts/evidencias/pagina.png
```

Captura do Grafana exige `GRAFANA_ADMIN_PASSWORD` definido no ambiente e recebe um caminho relativo ao Grafana:

```bash
node scripts/evidencias/web.mjs 'grafana:/d/vigia-sinais?from=now-15m&to=now&kiosk' scripts/evidencias/dashboard.png
```

Captura de terminal executa o comando real e renderiza a saída com Chromium, ocultando e-mails, IPv4 e valores com aparência de token:

```bash
bash scripts/evidencias/terminal.sh scripts/evidencias/alvos.png 'curl -fsS http://127.0.0.1:9090/api/v1/targets'
```

Revise cada PNG antes de compartilhá-lo. Os scripts ocultam e-mails e endereços IPv4 visíveis; não passe segredos como argumentos nem capture páginas privadas sem autenticação.

## Parar

```bash
docker compose down
```

Esse comando mantém os volumes de dados. Não use `down -v` para parar o serviço.
