from datetime import UTC, datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from vigia.clima import ClienteClima
from vigia.config import Settings
from vigia.main import criar_app
from vigia.relatos import RepositorioMemoria


@pytest.fixture
def client():
    with respx.mock:
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=httpx.Response(
                200,
                json={
                    "hourly": {
                        "time": ["2026-11-12T15:00"],
                        "precipitation": [35],
                        "precipitation_probability": [80],
                    }
                },
            )
        )
        http = httpx.AsyncClient()
        clima = ClienteClima(
            http,
            "https://api.open-meteo.com/v1/forecast",
            1800,
            lambda: datetime(2026, 11, 12, 14, tzinfo=UTC),
        )
        app = criar_app(
            Settings(ip_hash_secret="segredo"),
            RepositorioMemoria(),
            clima,
            lambda: datetime(2026, 11, 12, 14, tzinfo=UTC),
        )
        with TestClient(app, follow_redirects=False) as c:
            yield c
        import asyncio

        asyncio.run(http.aclose())


def test_home_capitais(client):
    r = client.get("/")
    assert "/municipio/1302603" in r.text and "/municipio/3509502" not in r.text


def test_busca_sem_resultado(client):
    assert "Nenhum município encontrado" in client.get("/buscar?q=zzzznope").text


def test_pagina_municipio_mostra_nivel(client):
    assert (
        "Alerta" in client.get("/municipio/3509502").text
        and "199" in client.get("/municipio/3509502").text
    )


def test_api_contrato(client):
    d = client.get("/api/municipios/3509502/previsao").json()
    assert set(d) == {
        "municipio",
        "nivel",
        "max_mm_hora",
        "total_mm_24h",
        "hora_pico",
        "obtida_em",
        "desatualizada",
        "horas",
    }


def test_nao_encontrado(client):
    assert (
        client.get("/municipio/9999999").status_code == 404
        and client.get("/municipio/abc").status_code == 404
    )


def test_relato_post(client):
    r = client.post(
        "/municipio/3509502/relatos",
        data={"bairro": "Centro", "referencia": "Rua central", "situacao": "agua_na_calcada"},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )
    assert r.status_code == 303


def test_limite_por_ip_encaminhado(client):
    dados = {"bairro": "Centro", "referencia": "Rua central", "situacao": "agua_na_calcada"}
    cabecalho = {"X-Forwarded-For": "203.0.113.7"}
    for _ in range(5):
        assert (
            client.post("/municipio/3509502/relatos", data=dados, headers=cabecalho).status_code
            == 303
        )
    assert (
        client.post("/municipio/3509502/relatos", data=dados, headers=cabecalho).status_code == 429
    )
    assert (
        client.post(
            "/municipio/3509502/relatos", data=dados, headers={"X-Forwarded-For": "198.51.100.9"}
        ).status_code
        == 303
    )
