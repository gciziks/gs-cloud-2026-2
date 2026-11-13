"""Coleta resumos reais para as capturas, sem valores de segredos."""

import json
import shutil
import subprocess
import sys
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def executar(*args):
    programa = shutil.which(args[0]) or args[0]
    return subprocess.check_output([programa, *args[1:]], cwd=RAIZ, text=True, encoding="utf-8")


def dados(*args):
    return json.loads(executar(*args))


tipo = sys.argv[1]
if tipo == "compose":
    print(executar("docker", "compose", "ps"))
elif tipo == "usuario":
    print(executar("docker", "compose", "exec", "-T", "app", "id"))
    print(executar("docker", "image", "ls", "vigia-chuva"))
elif tipo == "pipeline":
    run = dados("gh", "run", "view", sys.argv[2], "--json", "status,conclusion,url,jobs")
    print(run["url"], "\nEstado:", run["status"], run["conclusion"])
    for job in run["jobs"]:
        print(f"{job['name']:<15} {job['conclusion'] or job['status']}")
elif tipo == "secrets":
    for chave in dados("gh", "secret", "list", "--env", "producao", "--json", "name"):
        print("Secret OIDC:", chave["name"])
    for chave in dados("gh", "variable", "list", "--json", "name"):
        print("Variable:", chave["name"])
elif tipo == "custos":
    custos = json.loads((RAIZ / "docs/custos.json").read_text(encoding="utf-8"))
    print("Azure Retail Prices API |", custos["consulta"], "|", custos["regiao"])
    total = 0
    for item in custos["itens"]:
        valor = item["total_18_dias_usd"]
        total += valor
        print(f"{item['medidor']:<38} US$ {item['preco_unitario_usd']:.4f}/{item['unidade']}"
              f" | 18 dias: US$ {valor:.2f}")
    print(f"Subtotal fixo: US$ {total:.2f}")
    print(f"Reserva operacoes e trafego leve: US$ {custos['reserva_operacoes_usd']:.2f}")
    print(f"Estimativa por ate 18 dias: US$ {total + custos['reserva_operacoes_usd']:.2f}")
    print("Sem presumir gratuidade. Orcamento BRL60: aviso, nao corte automatico.")
elif tipo == "admin":
    ambiente = {**os.environ, "ARM_SUBSCRIPTION_ID": executar("az", "account", "show", "--query", "id", "-o", "tsv").strip()}
    r = subprocess.run([shutil.which("terraform"), "-chdir=infra/main", "plan",
                        "-var=admin_cidr=0.0.0.0/0", "-refresh=false", "-lock=false", "-no-color"],
                       cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", env=ambiente)
    print("terraform plan -var=admin_cidr=0.0.0.0/0")
    print("Codigo de saida:", r.returncode)
    saida = r.stdout + r.stderr
    print(saida[saida.find("Error: Invalid value for variable"):].strip())
    if r.returncode == 0 or "admin_cidr precisa" not in saida:
        raise SystemExit("Validacao esperada nao confirmada")
elif tipo == "trivy":
    scan = dados("docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock",
                 "-v", "vigia-trivy-cache:/root/.cache/trivy", "aquasec/trivy:0.76.1", "image",
                 "--quiet", "--severity", "HIGH,CRITICAL", "--ignore-unfixed", "--exit-code", "1",
                 "--format", "json", "vigia-chuva:local")
    vulnerabilidades = [v for r in scan.get("Results", []) for v in r.get("Vulnerabilities", [])]
    print("Trivy 0.76.1 | imagem vigia-chuva:local")
    print("Filtro: HIGH,CRITICAL; com correcao disponivel")
    print("HIGH:", sum(v["Severity"] == "HIGH" for v in vulnerabilidades))
    print("CRITICAL:", sum(v["Severity"] == "CRITICAL" for v in vulnerabilidades))
    print("Exit code do scan: 0")
    print("Os scans IaC e Dockerfile tambem sao gates do job imagem no Actions.")
elif tipo == "ntfy":
    d = json.loads((RAIZ / "docs/alerta.json").read_text(encoding="utf-8"))
    print("Notificacao real recebida pelo ntfy, sem divulgar o topico:")
    mensagem = d["notificacao"]
    print("Evento:", mensagem["event"], "| instante Unix:", mensagem["time"])
    print("Titulo:", mensagem["title"])
    print("Mensagem recebida (inicio):")
    print("\n".join(mensagem["message"].splitlines()[:12]))
elif tipo == "alerta":
    d = json.loads((RAIZ / "docs/alerta.json").read_text(encoding="utf-8"))
    e = d[sys.argv[2]]
    print("Grafana API | MVP fora do ar")
    print("Origem: /api/prometheus/grafana/api/v1/alerts")
    print("Instante observado UTC:", e["utc"])
    print("Estado observado:", e["estado"])
    for instancia in e["instancias"]:
        print("Regra:", instancia["labels"]["alertname"])
        print("Alvo:", instancia["labels"].get("instance"))
        print("Job:", instancia["labels"].get("job"))
        print("Estado da instancia:", instancia["state"])
    print("Captura automatizada da resposta real; dados em docs/alerta.json.")
elif tipo == "rollback":
    saida = executar("gh", "run", "view", sys.argv[2], "--log-failed")
    for linha in saida.splitlines():
        if "DEPLOY_FALHOU " in linha and "rollback para" in linha:
            print(linha)
    d = json.loads((RAIZ / "docs/rollback.json").read_text(encoding="utf-8"))
    print("Verificacao apos o rollback, UTC:", d["utc"])
    print("Imagem restaurada:", d["sha_restaurado"])
    print("Saude do container:", d["saude_container"])
    print("HTTPS:", json.dumps(d["respostas_https"]))
else:
    outputs = dados("terraform", "-chdir=infra/main", "output", "-json")
    def val(nome):
        return outputs[nome]["value"]
    rg = val("rg_nome")
    if tipo == "infra":
        for nome in ["url_publica", "vm_nome", "rg_nome", "acr_nome", "key_vault_nome"]:
            print(nome + ":", val(nome))
        vm = dados("az", "vm", "show", "-g", rg, "-n", val("vm_nome"),
                   "--query", "{regiao:location,tamanho:hardwareProfile.vmSize,discoGB:storageProfile.osDisk.diskSizeGB,tipo:storageProfile.osDisk.managedDisk.storageAccountType}", "-o", "json")
        print(json.dumps(vm, indent=2))
    elif tipo == "nsg":
        regras = dados("az", "network", "nsg", "rule", "list", "-g", rg,
                       "--nsg-name", "nsg-vigia", "-o", "json")
        for r in regras:
            print(r["name"], r["protocol"], r["destinationPortRange"], r["sourceAddressPrefix"])
        print("SSH aberto:", any(r["destinationPortRange"] == "22" for r in regras))
    elif tipo == "state":
        state = dados("terraform", "-chdir=infra/bootstrap", "output", "-json")
        storage = state["storage_account_name"]["value"]
        print(executar("az", "storage", "account", "show", "-g", "rg-vigia-chuva-tfstate",
                       "-n", storage, "--query", "{nome:name,tls:minimumTlsVersion,chaveCompartilhada:allowSharedKeyAccess,firewall:networkRuleSet.defaultAction}", "-o", "json"))
        print("Versionamento:", executar("az", "storage", "account", "blob-service-properties", "show",
                       "-g", "rg-vigia-chuva-tfstate", "--account-name", storage,
                       "--query", "isVersioningEnabled", "-o", "tsv").strip())
        print(executar("git", "check-ignore", "infra/main/terraform.tfvars", "infra/main/backend.hcl",
                       "infra/bootstrap/terraform.tfstate", "infra/main/main.tfplan"))
    elif tipo == "permissoes":
        principal = executar("az", "identity", "show", "-g", rg, "-n", "id-vigia-deploy",
                             "--query", "principalId", "-o", "tsv").strip()
        roles = dados("az", "role", "assignment", "list", "--assignee-object-id", principal,
                      "--all", "-o", "json")
        for role in roles:
            print(role["roleDefinitionName"], "|", role["scope"].split("/resourceGroups/")[-1])
    elif tipo == "host":
        print(executar("az", "vm", "run-command", "invoke", "-g", rg, "-n", val("vm_nome"),
                       "--command-id", "RunShellScript", "--scripts",
                       "cloud-init status; docker compose version; swapon --show; cd /opt/vigia && docker compose exec -T app id && echo ADMINISTRACAO_SEM_SSH_OK",
                       "--query", "value[0].message", "-o", "tsv"))
    else:
        raise SystemExit("Coleta desconhecida")
