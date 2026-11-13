from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class Nivel(StrEnum):
    SEM_ALERTA = "sem_alerta"
    ATENCAO = "atencao"
    ALERTA = "alerta"
    ALERTA_MAXIMO = "alerta_maximo"

    @property
    def rotulo(self) -> str:
        return {
            self.SEM_ALERTA: "Sem alerta",
            self.ATENCAO: "Atenção",
            self.ALERTA: "Alerta",
            self.ALERTA_MAXIMO: "Alerta máximo",
        }[self]


@dataclass(frozen=True)
class HoraPrevista:
    inicio: datetime
    precipitacao_mm: float
    probabilidade_pct: int | None


@dataclass(frozen=True)
class Avaliacao:
    nivel: Nivel
    max_mm_hora: float
    total_mm_24h: float
    hora_pico: datetime | None
    orientacao: str


def avaliar(horas: list[HoraPrevista], agora: datetime) -> Avaliacao:
    consideradas = [
        h for h in horas if agora - timedelta(hours=1) < h.inicio < agora + timedelta(hours=24)
    ]
    pico = max((h.precipitacao_mm for h in consideradas), default=0.0)
    total = sum(h.precipitacao_mm for h in consideradas)
    hora_pico = (
        next((h.inicio for h in consideradas if h.precipitacao_mm == pico), None)
        if pico > 0
        else None
    )
    if pico >= 60 or total >= 100:
        nivel = Nivel.ALERTA_MAXIMO
        orientacao = (
            "Há risco muito alto de chuva forte. Procure abrigo seguro e ligue 199 em emergência."
        )
    elif pico >= 30 or total >= 50:
        nivel = Nivel.ALERTA
        orientacao = (
            "A chuva pode causar alagamentos. Evite áreas alagadas e ligue 199 "
            "se houver emergência."
        )
    elif pico >= 20 or total >= 30:
        nivel = Nivel.ATENCAO
        orientacao = (
            "Acompanhe as condições e evite pontos de alagamento. Cadastre seu CEP "
            "para alertas por SMS no 40199."
        )
    else:
        nivel = Nivel.SEM_ALERTA
        orientacao = (
            "Não há previsão acima dos limiares de atenção. Acompanhe os avisos da Defesa Civil."
        )
    return Avaliacao(nivel, pico, total, hora_pico, orientacao)
