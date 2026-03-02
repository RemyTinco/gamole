"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    port: int = 3001
    host: str = "0.0.0.0"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gamole"

    # Auth
    session_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Rate limiting
    rate_limit_per_minute: int = 100

    # AI
    google_generative_ai_api_key: str = ""

    # GitHub (for cloning private repos during codebase indexing)
    github_token: str = ""

    # Linear (server-side token for syncing)
    linear_api_token: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
