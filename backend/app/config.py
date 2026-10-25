"""Settings from environment variables (.env in development). All secrets live here and only here."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: str = "dev"
    demo_mode: bool = False
    listener_debounce_seconds: float = Field(default=0.9, ge=0)
    listener_concurrency: int = Field(default=2, ge=1)
    google_maps_api_key: str = ""
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
    serpapi_concurrency: int = Field(default=4, ge=1)
    serpapi_timeout: float = Field(default=20, gt=0)
    serpapi_retries: int = Field(default=2, ge=0)
    serpapi_request_limit: int = Field(default=100, ge=1)
    flight_cache_seconds: int = Field(default=900, ge=0)
    lodging_cache_seconds: int = Field(default=1800, ge=0)
    empty_cache_seconds: int = Field(default=60, ge=0)

    # Capital One Nessie sandbox
    nessie_api_key: str = ""
    nessie_base_url: str = "http://api.nessieisreal.com"

    # Private budgets only shape options when the group is at least this big (smaller groups could infer them).
    min_group_size_for_private_budgets: int = Field(default=3, ge=3)


    @model_validator(mode="after")
    def local_demo_only(self):
        if self.demo_mode and self.app_env != "dev":
            raise ValueError("DEMO_MODE is only available with APP_ENV=dev")
        return self

    @property
    def effective_database_url(self) -> str:
        # Demo data can never be written into the configured Supabase database.
        return "sqlite:///./instaplan-demo.db" if self.demo_mode else self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
