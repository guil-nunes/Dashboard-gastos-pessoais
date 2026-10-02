from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_path: Path = Path("data/gastos.db")
    backups_dir: Path = Path("backups")
    backups_keep: int = 10
    gemini_enabled: bool = False
    gemini_api_key: str | None = None

    @field_validator("database_path", "backups_dir")
    @classmethod
    def resolve_from_repo_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else REPO_ROOT / value


@lru_cache
def get_settings() -> Settings:
    return Settings()
