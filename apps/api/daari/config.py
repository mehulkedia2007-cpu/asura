"""Settings — the only place apps/api reads the repo-root .env from.

pydantic-settings only; never read `.env` with open()/dotenv directly elsewhere.
NEVER log or echo a value from this module. `__repr_args__` is overridden (not
just `__repr__`) because pydantic v2's `BaseModel.__str__` and `__repr__` both
build their output from `__repr_args__` — overriding only `__repr__` would still
let `str(settings)` leak a secret.
"""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local infra — non-secret, defaults match docker-compose.yml / .env.example.
    DATABASE_URL: str = "postgresql+asyncpg://daari:daari@localhost:5432/daari"
    DATABASE_URL_UNPOOLED: str | None = None
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "KV_URL", "UPSTASH_REDIS_URL"),
    )
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # LLM / live-source keys — secret, optional, never defaulted to a real value.
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    ADZUNA_APP_ID: str | None = None
    ADZUNA_APP_KEY: str | None = None
    SERPAPI_KEY: str | None = None
    SERPAPI_MONTHLY_BUDGET: int = 100

    # App config — non-secret.
    LLM_CACHE_DIR: str = ".cache/llm"
    TTS_VOICE_TE: str = "te-IN-ShrutiNeural"
    TTS_VOICE_HI: str = "hi-IN-SwaraNeural"
    TTS_VOICE_EN: str = "en-IN-NeerjaNeural"
    DAARI_SEED: int = 1337
    APP_ENV: str = "local"
    LOG_LEVEL: str = "info"
    DEFAULT_DISTRICT: str = "Guntur"
    VERCEL: bool = False
    CACHE_ROOT: str | None = None
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3015"

    @property
    def database_url(self) -> str:
        # Neon injects both URLs. Direct connections avoid PgBouncer statement
        # name collisions; NullPool releases connections after each operation.
        return self.DATABASE_URL_UNPOOLED or self.DATABASE_URL

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def __repr_args__(self):
        """Both __repr__ and __str__ derive from this in pydantic v2 — keep it secret-free."""
        return [("app_env", self.APP_ENV)]


settings = Settings()


def cache_root(repo_root: Path = REPO_ROOT) -> Path:
    """Keep local replay behavior; serverless filesystems only permit /tmp writes."""
    if settings.CACHE_ROOT:
        return Path(settings.CACHE_ROOT)
    return Path("/tmp/daari-cache") if settings.VERCEL else repo_root / ".cache"
