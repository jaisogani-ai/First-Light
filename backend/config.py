"""Runtime configuration loaded from environment / .env (never committed)."""

import secrets
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Loads .env into the real process environment (not just this Settings object) so
# ANTHROPIC_API_KEY — read directly by the Anthropic SDK's default credential
# resolution, not through pydantic-settings — can live in the same .env file.
load_dotenv()

_SECRET_KEY_FILE = Path(__file__).resolve().parent.parent / ".pcc_secret_key"


def _resolve_default_secret_key() -> str:
    """Only invoked when FIRST_LIGHT_HMAC_SECRET_KEY isn't set via env/.env. A fresh random
    key generated on every process start would silently invalidate every previously-issued
    certificate (and desync multiple workers), so the generated key is persisted to a local,
    gitignored file and reused on subsequent runs instead."""
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    return key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FIRST_LIGHT_")

    database_url: str = "sqlite:///./first_light.db"
    hmac_secret_key: str = Field(default_factory=_resolve_default_secret_key)
    rate_limit_per_minute: int = 60
    default_mission_profile: str = "earth_observation"


settings = Settings()
