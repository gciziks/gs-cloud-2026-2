"""Preenche somente os segredos locais que ainda estão vazios ou com marcador."""

import secrets
from pathlib import Path

arquivo = Path(".env")
texto = arquivo.read_text(encoding="utf-8") if arquivo.exists() else Path(".env.example").read_text(encoding="utf-8")
chaves = {"POSTGRES_PASSWORD", "IP_HASH_SECRET", "METRICS_TOKEN"}
linhas = []
for linha in texto.splitlines():
    if "=" in linha:
        nome, valor = linha.split("=", 1)
        if nome in chaves and (not valor or valor == "troque-por-um-valor-longo"):
            linha = nome + "=" + secrets.token_urlsafe(32)
    linhas.append(linha)
arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
arquivo.chmod(0o600)
print("Configuracao local preparada; segredos existentes foram preservados.")
