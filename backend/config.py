"""Runtime configuration loaded from environment / .env (never committed)."""

import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FIRST_LIGHT_")

    database_url: str = "sqlite:///./first_light.db"
    hmac_secret_key: str = secrets.token_hex(32)
    rate_limit_per_minute: int = 60
    default_mission_profile: str = "earth_observation"


settings = Settings()
