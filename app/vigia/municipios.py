import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Municipio:
    codigo_ibge: int
    nome: str
    uf: str
    latitude: float
    longitude: float
    fuso: str


def carregar_municipios(caminho: Path) -> dict[int, Municipio]:
    import csv

    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = csv.DictReader(arquivo)
        return {
            int(linha["codigo_ibge"]): Municipio(
                int(linha["codigo_ibge"]),
                linha["nome"],
                linha["uf"],
                float(linha["latitude"]),
                float(linha["longitude"]),
                linha["fuso"],
            )
            for linha in linhas
        }


def _normalizar(texto: str) -> str:
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(caractere)
    )


def buscar(municipios: dict[int, Municipio], termo: str, limite: int = 10) -> list[Municipio]:
    consulta = _normalizar(termo.strip())
    if len(consulta) < 2 or limite <= 0:
        return []
    encontrados = [m for m in municipios.values() if consulta in _normalizar(m.nome)]
    encontrados.sort(
        key=lambda m: (not _normalizar(m.nome).startswith(consulta), _normalizar(m.nome), m.uf)
    )
    return encontrados[:limite]
