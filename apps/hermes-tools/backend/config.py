"""Centralized configuration — reads the same env var names the Ansible role
templates into .env, so this file is the single place that maps env -> app.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    telegram_bot_token: str = ""
    allowed_user_ids: str = ""  # comma-separated Telegram numeric IDs
    telegram_auth_enforce: bool = True

    hf_token: str = ""
    mcp_api_key: str = ""
    # comma-separated Host header values FastMCP's DNS-rebinding protection accepts
    mcp_allowed_hosts: str = "localhost,127.0.0.1"

    upload_dir: Path = Path("/app/uploads")

    sam_model_path: str = "/app/models/sam_vit_b_01ec64.pth"
    sam_model_type: str = "vit_b"
    sam_device: str = "cpu"

    mini_app_url: str = "https://hermes-tools.batistela.tech/"

    @property
    def allowed_user_id_set(self) -> set[int]:
        result: set[int] = set()
        for raw in self.allowed_user_ids.split(","):
            raw = raw.strip()
            if raw:
                try:
                    result.add(int(raw))
                except ValueError:
                    continue
        return result

    @property
    def mcp_allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.mcp_allowed_hosts.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
