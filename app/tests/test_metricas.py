from fastapi import FastAPI
from fastapi.testclient import TestClient

from vigia.metricas import instalar_metricas


def test_metricas_expoem_histograma_e_template_da_rota():
    app = FastAPI()
    instalar_metricas(app)

    @app.get("/municipio/{codigo}")
    def cidade(codigo):
        return {"codigo": codigo}

    c = TestClient(app, raise_server_exceptions=False)
    c.get("/municipio/3509502")
    body = c.get("/metrics").text
    assert 'route="/municipio/{codigo}"' in body and "http_request_duration_seconds_bucket" in body


def test_caminho_desconhecido_nao_vira_label_dinamico():
    app = FastAPI()
    instalar_metricas(app)
    c = TestClient(app, raise_server_exceptions=False)
    c.get("/wp-admin")
    body = c.get("/metrics").text
    assert 'route="nao_mapeada"' in body and "/wp-admin" not in body


def test_excecao_conta_status_500():
    app = FastAPI()
    instalar_metricas(app)

    @app.get("/falha")
    def falha():
        raise RuntimeError("falha de teste")

    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/falha").status_code == 500
    assert 'route="/falha",status="500"' in client.get("/metrics").text
