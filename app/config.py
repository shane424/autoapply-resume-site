import yaml
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.models.settings import AppSettings

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""


def load_app_settings() -> AppSettings:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
        return AppSettings(**data)
    return AppSettings()


def save_app_settings(settings: AppSettings) -> None:
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(settings.model_dump(), f, default_flow_style=False, allow_unicode=True)


env_settings = EnvSettings()
