from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from vigia.clima import ClienteClima, PrevisaoIndisponivel
from vigia.municipios import Municipio

M = Municipio(1302603, "Manaus", "AM", -3.1, -60.0, "America/Manaus")


def payload(chuva=2):
    return {
        "hourly": {
            "time": ["2026-11-12T00:00", "2026-11-12T01:00"],
            "precipitation": [chuva, None],
            "precipitation_probability": [70, 0],
        }
    }


@pytest.mark.asyncio
@respx.mock
async def test_converte_horas_e_parametros():
    rota = respx.get("https://tempo.test/forecast").mock(
        return_value=httpx.Response(200, json=payload())
    )
    c = ClienteClima(
        httpx.AsyncClient(),
        "https://tempo.test/forecast",
        1800,
        lambda: datetime(2026, 11, 12, tzinfo=UTC),
    )
    p = await c.previsao(M)
    assert (
        p.horas[0].inicio.tzinfo == ZoneInfo("America/Manaus") and p.horas[1].precipitacao_mm == 0
    )
    assert rota.calls[0].request.url.params["timezone"] == "America/Manaus"
    assert rota.calls[0].request.url.params["forecast_days"] == "3"
    await c.http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_cache_ttl_e_fallback():
    route = respx.get("https://tempo.test").mock(
        side_effect=[httpx.Response(200, json=payload()), httpx.Response(503)]
    )
    instante = [datetime(2026, 11, 12, tzinfo=UTC)]
    c = ClienteClima(httpx.AsyncClient(), "https://tempo.test", 1800, lambda: instante[0])
    await c.previsao(M)
    instante[0] += timedelta(minutes=10)
    await c.previsao(M)
    assert route.call_count == 1
    instante[0] += timedelta(minutes=31)
    antigo = await c.previsao(M)
    assert route.call_count == 2 and antigo.desatualizada
    await c.http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_erro_sem_cache():
    respx.get("https://tempo.test").mock(return_value=httpx.Response(503))
    c = ClienteClima(httpx.AsyncClient(), "https://tempo.test", 1)
    with pytest.raises(PrevisaoIndisponivel):
        await c.previsao(M)
    await c.http.aclose()
