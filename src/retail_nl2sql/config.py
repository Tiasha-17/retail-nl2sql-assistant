"""Application settings resolved independently of the process working directory."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_path: Path = Field(
        default=PROJECT_ROOT / "data" / "retail_star_schema.db",
        validation_alias=AliasChoices("RETAIL_DATABASE_PATH", "DATABASE_PATH"),
    )
    llm_provider: str = Field(default="ollama", validation_alias="RETAIL_LLM_PROVIDER")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="qwen2.5:7b-instruct", validation_alias="OLLAMA_MODEL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-6-luna", validation_alias="OPENAI_MODEL")
    llm_timeout_seconds: float = Field(
        default=120,
        ge=1,
        le=600,
        validation_alias="RETAIL_LLM_TIMEOUT_SECONDS",
    )
    max_rows: int = Field(default=100, ge=1, le=1000, validation_alias="RETAIL_MAX_ROWS")
    query_timeout_ms: int = Field(
        default=2000,
        ge=10,
        le=30_000,
        validation_alias="RETAIL_QUERY_TIMEOUT_MS",
    )
    schema_sample_rows: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias="RETAIL_SCHEMA_SAMPLE_ROWS",
    )

    def resolved_database_path(self) -> Path:
        path = self.database_path
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()
