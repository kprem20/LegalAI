from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNAVAILABLE = "Information not available in the dataset."


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_persist_directory: str = "chroma_data"
    chroma_collection: str = "nyayasearch_chunks"
    dataset_dir: str = "dataset"
    app_db_path: str = "data/app.db"
    default_top_k: int = 5
    candidate_multiplier: int = 8
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    secret_key: str = "nyayasearch-local-dev"
    index_years: str = ""
    index_max_files: int | None = None

    @property
    def dataset_path(self) -> Path:
        path = Path(self.dataset_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def chroma_path(self) -> Path:
        path = Path(self.chroma_persist_directory)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def app_db(self) -> Path:
        path = Path(self.app_db_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
