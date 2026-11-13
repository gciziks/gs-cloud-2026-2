import hashlib
import hmac
from datetime import date


def hash_ip(ip: str, segredo: bytes, dia: date) -> str:
    mensagem = f"{dia.isoformat()}|{ip}".encode()
    return hmac.new(segredo, mensagem, hashlib.sha256).hexdigest()
