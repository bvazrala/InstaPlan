"""Settings from environment variables (.env in development). All secrets live here and only here."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    frontend_origin: str = "http://localhost:3000"

    # Supabase Postgres in production: postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres
    database_url: str = "sqlite:///./instaplan.db"

    # Supabase Auth (Settings → API Keys)
    supabase_url: str = ""
    supabase_publishable_key: str = ""  # sb_publishable_...
    supabase_secret_key: str = ""  # sb_secret_... seed script only; never used by the API

    # Fernet key for private columns. Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    private_data_key: str = ""

    # Meta Muse Spark (OpenAI-compatible Meta Model API): the group assistant and the private check-ins.
    # Standard models only: "-contributor" models may use prompts for training (muse_client.py refuses them).
    muse_api_key: str = ""
    muse_base_url: str = "https://api.meta.ai/v1"
    muse_model: str = "muse-spark-1.3"

    serpapi_key: str = ""

    # Capital One Nessie sandbox
    nessie_api_key: str = ""
    nessie_base_url: str = "http://api.nessieisreal.com"

    # Private budgets only shape options when the group is at least this big (smaller groups could infer them).
    min_group_size_for_private_budgets: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
