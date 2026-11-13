from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from vigia.risco import HoraPrevista, Nivel, avaliar

SP = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 12, 14, 30, tzinfo=SP)


def horas(valores, inicio=datetime(2026, 11, 12, 14, tzinfo=SP)):
    return [HoraPrevista(inicio + timedelta(hours=i), v, None) for i, v in enumerate(valores)]


@pytest.mark.parametrize(
    "valores,nivel",
    [
        ([0.0] * 24, Nivel.SEM_ALERTA),
        ([19.9] + [0] * 23, Nivel.SEM_ALERTA),
        ([20.0] + [0] * 23, Nivel.ATENCAO),
        ([1.25] * 24, Nivel.ATENCAO),
        ([30.0] + [0] * 23, Nivel.ALERTA),
        ([2.5] * 20 + [0] * 4, Nivel.ALERTA),
        ([60.0] + [0] * 23, Nivel.ALERTA_MAXIMO),
        ([5.0] * 20 + [0] * 4, Nivel.ALERTA_MAXIMO),
    ],
)
def test_limiares(valores, nivel):
    assert avaliar(horas(valores), AGORA).nivel == nivel


def test_janela_hora_pico_e_totais():
    a = avaliar(horas([0, 3, 12, 12, 1] + [0] * 19), AGORA)
    assert (a.max_mm_hora, a.total_mm_24h, a.hora_pico) == (
        12,
        28,
        datetime(2026, 11, 12, 16, tzinfo=SP),
    )


def test_orientacao_cita_defesa_civil():
    assert "199" in avaliar(horas([30.0] + [0] * 23), AGORA).orientacao
