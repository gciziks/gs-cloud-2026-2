from pathlib import Path

import pytest

from vigia.municipios import carregar_municipios


@pytest.fixture(scope="session")
def municipios():
    return carregar_municipios(Path(__file__).parents[1] / "vigia/dados/municipios.csv")
