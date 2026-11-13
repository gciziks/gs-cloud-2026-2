from datetime import UTC, datetime, timedelta

import pytest

from vigia.relatos import (
    ErroValidacao,
    LimiteExcedido,
    NovoRelato,
    RepositorioMemoria,
    Situacao,
    registrar,
    validar,
)

AGORA = datetime(2026, 1, 10, tzinfo=UTC)


def novo(bairro="Centro"):
    return NovoRelato(3509502, bairro, "Rua das Flores", Situacao.AGUA_NA_CALCADA)


def test_validar_limpa_espacos():
    assert (
        validar(
            {
                "bairro": "  Jardim   América ",
                "referencia": " Rua central ",
                "situacao": "agua_na_calcada",
            },
            1,
        ).bairro
        == "Jardim América"
    )


@pytest.mark.parametrize(
    "dados,campo",
    [
        ({"bairro": "", "referencia": "abc", "situacao": "agua_na_calcada"}, "bairro"),
        ({"bairro": "x" * 81, "referencia": "abc", "situacao": "agua_na_calcada"}, "bairro"),
        ({"bairro": "ok", "referencia": "ab", "situacao": "agua_na_calcada"}, "referencia"),
        ({"bairro": "ok", "referencia": "abc", "situacao": "tsunami"}, "situacao"),
        (
            {
                "bairro": "ok",
                "referencia": "abc",
                "situacao": "agua_na_calcada",
                "site": "http://spam",
            },
            "site",
        ),
    ],
)
def test_validacao(dados, campo):
    with pytest.raises(ErroValidacao) as e:
        validar(dados, 1)
    assert campo in e.value.campos


@pytest.mark.asyncio
async def test_limite_e_retencao():
    repo = RepositorioMemoria()
    for i in range(5):
        await registrar(
            repo, novo(), "hash", AGORA - timedelta(minutes=8) + timedelta(minutes=i), 5
        )
    with pytest.raises(LimiteExcedido):
        await registrar(repo, novo(), "hash", AGORA, 5)
    await registrar(repo, novo(), "outro", AGORA, 5)
    await repo.inserir(novo(), "antigo", AGORA - timedelta(hours=25))
    await repo.inserir(novo(), "velho", AGORA - timedelta(days=8))
    assert await repo.aplicar_retencao(AGORA) == (1, 1)
    assert await repo.listar_recentes(3509502, AGORA - timedelta(days=1))
