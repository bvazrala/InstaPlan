"""Settings from environment variables (.env in development). All secrets live here and only here."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    frontend_origin: str = "http://localhost:3000"

    # Supabase Postgres in production: postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres
    database_url: str = "sqlite:///./instaplan.db"

    # Supabase Auth
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_service_role_key: str = ""  # seed script only; never used by the API

    # Fernet key for private columns. Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    private_data_key: str = ""

    # Meta Muse Spark (OpenAI-compatible Meta Model API). Confirm both values at the Meta booth.
    muse_api_key: str = ""
    muse_base_url: str = "https://api.meta.ai/v1"
    muse_model: str = "muse-spark-1.1"

    # Gemini: use a key from a billing-enabled project so prompts are not used for training.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    serpapi_key: str = ""

    # Capital One Nessie sandbox
    nessie_api_key: str = ""
    nessie_base_url: str = "http://api.nessieisreal.com"

    # Private budgets only shape options when the group is at least this big (smaller groups could infer them).
    min_group_size_for_private_budgets: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
