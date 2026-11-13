"""Gera CSV combinando nomes e códigos oficiais do IBGE com coordenadas e fuso."""

import csv
import gzip
import io
import json
import urllib.request
from pathlib import Path

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
BASE_KELVINS = (
    "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/"
)
DESTINO = Path(__file__).resolve().parents[1] / "app/vigia/dados/municipios.csv"


def baixar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "VigiaDaChuva/1.0"})
    dados = urllib.request.urlopen(req, timeout=30).read()
    return gzip.decompress(dados) if dados[:2] == b"\x1f\x8b" else dados


def gerar() -> int:
    municipios = json.loads(baixar(URL_IBGE))
    leitor = csv.DictReader(
        io.StringIO(baixar(BASE_KELVINS + "municipios.csv").decode("utf-8-sig"))
    )
    coordenadas = {int(linha["codigo_ibge"]): linha for linha in leitor}
    estados = csv.DictReader(
        io.StringIO(baixar(BASE_KELVINS + "estados.csv").decode("utf-8-sig"))
    )
    siglas = {int(linha["codigo_uf"]): linha["uf"] for linha in estados}
    fusos_corrigidos = {1302603: "America/Manaus"}
    linhas = []
    ausentes = []
    for item in municipios:
        codigo = int(item["id"])
        coord = coordenadas.get(codigo)
        if coord is None:
            ausentes.append(codigo)
            continue
        uf_codigo = int(str(codigo)[:2])
        linhas.append(
            {
                "codigo_ibge": codigo,
                "nome": item["nome"],
                "uf": siglas[uf_codigo],
                "latitude": coord["latitude"],
                "longitude": coord["longitude"],
                "fuso": fusos_corrigidos.get(codigo, coord["fuso_horario"]),
            }
        )
    if ausentes:
        raise ValueError(f"Sem coordenadas para códigos IBGE: {ausentes}")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(sorted(linhas, key=lambda linha: linha["codigo_ibge"]))
    return len(linhas)


if __name__ == "__main__":
    print(f"{gerar()} municípios gravados")
