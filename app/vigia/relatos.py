from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class Situacao(StrEnum):
    AGUA_NA_CALCADA = "agua_na_calcada"
    RUA_INTRANSITAVEL = "rua_intransitavel"
    IMOVEL_ATINGIDO = "imovel_atingido"

    @property
    def rotulo(self) -> str:
        return {
            self.AGUA_NA_CALCADA: "água na calçada",
            self.RUA_INTRANSITAVEL: "Rua intransitável",
            self.IMOVEL_ATINGIDO: "Imóvel atingido",
        }[self]


@dataclass(frozen=True)
class NovoRelato:
    codigo_ibge: int
    bairro: str
    referencia: str
    situacao: Situacao


@dataclass(frozen=True)
class Relato:
    id: int
    codigo_ibge: int
    bairro: str
    referencia: str
    situacao: Situacao
    criado_em: datetime


class ErroValidacao(Exception):
    def __init__(self, campos: dict[str, str]):
        self.campos = campos


class LimiteExcedido(Exception):
    pass


def validar(dados: Mapping[str, str], codigo_ibge: int) -> NovoRelato:
    def limpar(valor: str) -> str:
        return " ".join(valor.strip().split())

    bairro, referencia = limpar(dados.get("bairro", "")), limpar(dados.get("referencia", ""))
    campos = {}
    if dados.get("site", "").strip():
        campos["site"] = "Não foi possível validar o envio."
    if not 2 <= len(bairro) <= 80:
        campos["bairro"] = "Informe um bairro entre 2 e 80 caracteres."
    if not 3 <= len(referencia) <= 120:
        campos["referencia"] = "Informe uma referência entre 3 e 120 caracteres."
    try:
        situacao = Situacao(dados.get("situacao", ""))
    except ValueError:
        campos["situacao"] = "Selecione uma situação válida."
        situacao = Situacao.AGUA_NA_CALCADA
    if campos:
        raise ErroValidacao(campos)
    return NovoRelato(codigo_ibge, bairro, referencia, situacao)


class RepositorioRelatos(Protocol):
    async def inserir(self, relato: NovoRelato, ip_hash: str, agora: datetime) -> Relato: ...
    async def contar_por_ip(self, ip_hash: str, desde: datetime) -> int: ...
    async def listar_recentes(
        self, codigo_ibge: int, desde: datetime, limite: int = 20
    ) -> list[Relato]: ...
    async def aplicar_retencao(self, agora: datetime) -> tuple[int, int]: ...
    async def pronto(self) -> bool: ...


class RepositorioMemoria:
    def __init__(self):
        self.registros: list[tuple[Relato, str | None]] = []
        self.proximo_id = 1

    async def inserir(self, novo, ip_hash, agora):
        relato = Relato(
            self.proximo_id, novo.codigo_ibge, novo.bairro, novo.referencia, novo.situacao, agora
        )
        self.proximo_id += 1
        self.registros.append((relato, ip_hash))
        return relato

    async def contar_por_ip(self, ip_hash, desde):
        return sum(h == ip_hash and r.criado_em >= desde for r, h in self.registros)

    async def listar_recentes(self, codigo_ibge, desde, limite=20):
        return [
            r
            for r, _ in sorted(self.registros, key=lambda x: x[0].criado_em, reverse=True)
            if r.codigo_ibge == codigo_ibge and r.criado_em >= desde
        ][:limite]

    async def aplicar_retencao(self, agora):
        antes = len(self.registros)
        self.registros = [
            (relato, ip_hash)
            for relato, ip_hash in self.registros
            if relato.criado_em >= agora - timedelta(days=7)
        ]
        apagados = antes - len(self.registros)
        anonimizados = 0
        atualizados = []
        for relato, ip_hash in self.registros:
            if ip_hash is not None and relato.criado_em < agora - timedelta(hours=24):
                ip_hash = None
                anonimizados += 1
            atualizados.append((relato, ip_hash))
        self.registros = atualizados
        return anonimizados, apagados

    async def pronto(self):
        return True


class RepositorioPostgres:
    def __init__(self, pool):
        self.pool = pool

    @asynccontextmanager
    async def limitar(self, ip_hash):
        async with self.pool.connection() as conexao:
            async with conexao.transaction():
                # Serializa contagem e inserção do mesmo IP entre requisições simultâneas.
                await conexao.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (ip_hash,)
                )
                yield conexao

    @classmethod
    async def conectar(cls, dsn):
        from psycopg_pool import AsyncConnectionPool

        pool = AsyncConnectionPool(dsn, open=False)
        await pool.open()
        async with pool.connection() as conn:
            await conn.execute((Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8"))
        return cls(pool)

    async def inserir(self, r, ip_hash, agora):
        async with self.pool.connection() as c:
            cur = await c.execute(
                "INSERT INTO relatos "
                "(codigo_ibge,bairro,referencia,situacao,ip_hash,criado_em) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (r.codigo_ibge, r.bairro, r.referencia, r.situacao.value, ip_hash, agora),
            )
            return Relato(
                (await cur.fetchone())[0], r.codigo_ibge, r.bairro, r.referencia, r.situacao, agora
            )

    async def contar_por_ip(self, ip_hash, desde):
        async with self.pool.connection() as c:
            cur = await c.execute(
                "SELECT count(*) FROM relatos WHERE ip_hash=%s AND criado_em >= %s",
                (ip_hash, desde),
            )
            return (await cur.fetchone())[0]

    async def listar_recentes(self, codigo_ibge, desde, limite=20):
        async with self.pool.connection() as c:
            cur = await c.execute(
                "SELECT id,codigo_ibge,bairro,referencia,situacao,criado_em "
                "FROM relatos WHERE codigo_ibge=%s AND criado_em >= %s "
                "ORDER BY criado_em DESC LIMIT %s",
                (codigo_ibge, desde, limite),
            )
            return [
                Relato(i, ci, b, r, Situacao(s), dt) for i, ci, b, r, s, dt in await cur.fetchall()
            ]

    async def aplicar_retencao(self, agora):
        async with self.pool.connection() as c:
            b = await c.execute(
                "DELETE FROM relatos WHERE criado_em < %s", (agora - timedelta(days=7),)
            )
            a = await c.execute(
                "UPDATE relatos SET ip_hash=NULL WHERE ip_hash IS NOT NULL AND criado_em < %s",
                (agora - timedelta(hours=24),),
            )
            return a.rowcount, b.rowcount

    async def pronto(self):
        try:
            async with self.pool.connection() as c:
                await c.execute("SELECT 1")
            return True
        except Exception:
            return False


async def registrar(repo, relato, ip_hash, agora, limite_por_hora):
    if isinstance(repo, RepositorioPostgres):
        async with repo.limitar(ip_hash) as conexao:
            cursor = await conexao.execute(
                "SELECT count(*) FROM relatos WHERE ip_hash=%s AND criado_em >= %s",
                (ip_hash, agora - timedelta(hours=1)),
            )
            if (await cursor.fetchone())[0] >= limite_por_hora:
                raise LimiteExcedido
            cursor = await conexao.execute(
                "INSERT INTO relatos "
                "(codigo_ibge,bairro,referencia,situacao,ip_hash,criado_em) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (
                    relato.codigo_ibge,
                    relato.bairro,
                    relato.referencia,
                    relato.situacao.value,
                    ip_hash,
                    agora,
                ),
            )
            return Relato(
                (await cursor.fetchone())[0],
                relato.codigo_ibge,
                relato.bairro,
                relato.referencia,
                relato.situacao,
                agora,
            )
    if await repo.contar_por_ip(ip_hash, agora - timedelta(hours=1)) >= limite_por_hora:
        raise LimiteExcedido
    return await repo.inserir(relato, ip_hash, agora)
