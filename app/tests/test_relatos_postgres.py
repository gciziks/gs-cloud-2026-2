import asyncio
import os
from datetime import UTC, datetime

import pytest

from vigia.relatos import LimiteExcedido, NovoRelato, RepositorioPostgres, Situacao, registrar

pytestmark = pytest.mark.postgres
DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL nao definido"),
]


@pytest.mark.asyncio
async def test_limite_postgres():
    repo = await RepositorioPostgres.conectar(DSN)
    agora = datetime.now(UTC)
    relato = NovoRelato(3509502, "Centro", "Rua central", Situacao.AGUA_NA_CALCADA)
    try:
        async with repo.pool.connection() as conn:
            await conn.execute("DELETE FROM relatos WHERE codigo_ibge=%s", (3509502,))
        for _ in range(5):
            await registrar(repo, relato, "a" * 64, agora, 5)
        with pytest.raises(LimiteExcedido):
            await registrar(repo, relato, "a" * 64, agora, 5)
        resultados = await asyncio.gather(
            *(registrar(repo, relato, "b" * 64, agora, 5) for _ in range(12)),
            return_exceptions=True,
        )
        assert sum(not isinstance(r, Exception) for r in resultados) == 5
        assert sum(isinstance(r, LimiteExcedido) for r in resultados) == 7
    finally:
        async with repo.pool.connection() as conn:
            await conn.execute("DELETE FROM relatos WHERE codigo_ibge=%s", (3509502,))
        await repo.pool.close()
