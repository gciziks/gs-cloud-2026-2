from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from .metricas import registrar_chamada_clima
from .municipios import Municipio
from .risco import HoraPrevista


class PrevisaoIndisponivel(Exception):
    pass


@dataclass(frozen=True)
class Previsao:
    horas: list[HoraPrevista]
    obtida_em: datetime
    desatualizada: bool


class ClienteClima:
    def __init__(
        self,
        http: httpx.AsyncClient,
        url: str,
        ttl_segundos: int,
        relogio: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.http, self.url, self.ttl, self.relogio = http, url, ttl_segundos, relogio
        self.cache: dict[int, Previsao] = {}

    async def previsao(self, municipio: Municipio) -> Previsao:
        agora = self.relogio()
        antiga = self.cache.get(municipio.codigo_ibge)
        if antiga and (agora - antiga.obtida_em).total_seconds() < self.ttl:
            registrar_chamada_clima("cache")
            return antiga
        try:
            resposta = await self.http.get(
                self.url,
                params={
                    "latitude": municipio.latitude,
                    "longitude": municipio.longitude,
                    "hourly": "precipitation,precipitation_probability",
                    "timezone": municipio.fuso,
                    "forecast_days": 3,
                },
            )
            resposta.raise_for_status()
            dados = resposta.json()["hourly"]
            tempos, chuvas = dados["time"], dados["precipitation"]
            probabilidades = dados["precipitation_probability"]
            if len(tempos) != len(chuvas) or len(tempos) != len(probabilidades):
                raise ValueError("listas com tamanhos diferentes")
            zona = ZoneInfo(municipio.fuso)
            horas = [
                HoraPrevista(datetime.fromisoformat(t).replace(tzinfo=zona), float(c or 0), p)
                for t, c, p in zip(tempos, chuvas, probabilidades)
            ]
            previsao = Previsao(horas, agora, False)
            self.cache[municipio.codigo_ibge] = previsao
            registrar_chamada_clima("ok")
            return previsao
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as erro:
            if antiga:
                registrar_chamada_clima("stale")
                return Previsao(antiga.horas, antiga.obtida_em, True)
            registrar_chamada_clima("erro")
            raise PrevisaoIndisponivel from erro
