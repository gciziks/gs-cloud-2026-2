def test_carrega_todos_os_municipios(municipios):
    assert len(municipios) == 5571
    assert municipios[3509502].nome == "Campinas" and municipios[3509502].uf == "SP"


def test_fuso_de_manaus(municipios):
    assert municipios[1302603].fuso == "America/Manaus"


def test_busca_ignora_acento_e_caixa(municipios):
    from vigia.municipios import buscar

    assert buscar(municipios, "sao paulo")[0].codigo_ibge == 3550308


def test_prefixo_vem_antes(municipios):
    from vigia.municipios import buscar

    assert buscar(municipios, "campin")[0].nome.startswith("Campin")


def test_termo_curto(municipios):
    from vigia.municipios import buscar

    assert buscar(municipios, "a") == []
