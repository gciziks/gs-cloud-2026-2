from datetime import date

from vigia.privacidade import hash_ip


def test_hash_estavel_por_dia():
    assert hash_ip("203.0.113.7", b"segredo", date(2026, 1, 1)) == hash_ip(
        "203.0.113.7", b"segredo", date(2026, 1, 1)
    )


def test_hash_muda_de_dia_e_nao_expoe_ip():
    h = hash_ip("203.0.113.7", b"segredo", date(2026, 1, 1))
    assert h != hash_ip("203.0.113.7", b"segredo", date(2026, 1, 2)) and "203.0.113.7" not in h
