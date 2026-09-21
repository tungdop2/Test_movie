"""Load settings from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    openai_base_url: str | None
    data_dir: Path

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


def _normalize_model_name(raw: str) -> str:
    """Accept `gpt-…` or `openai:gpt-…` (same style as E-Commerce-AI)."""
    model = raw.strip()
    if ":" in model:
        provider, name = model.split(":", 1)
        if provider.strip().lower() == "openai":
            model = name.strip()
    return model or "gpt-5.4-mini"


def get_settings() -> Settings:
    key = os.getenv("OPENAI_API_KEY", "").strip() or None
    model = _normalize_model_name(os.getenv("OPENAI_MODEL", "openai:gpt-5.4-mini"))
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    data_dir_raw = os.getenv("DATA_DIR", "").strip()
    data_dir = (
        Path(data_dir_raw)
        if data_dir_raw
        else REPO_ROOT / "data" / "ml-latest-small-filtered"
    )
    return Settings(
        openai_api_key=key,
        openai_model=model,
        openai_base_url=base_url,
        data_dir=data_dir,
    )
