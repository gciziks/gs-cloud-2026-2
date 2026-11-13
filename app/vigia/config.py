from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str = "postgresql://vigia:vigia@localhost:5432/vigia"
    ip_hash_secret: SecretStr = SecretStr("troque-por-um-valor-longo")
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    cache_ttl_segundos: int = 1800
    timeout_upstream_segundos: float = 5
    limite_relatos_por_hora: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
