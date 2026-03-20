"""
Core configuration and settings.
"""
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent.parent


class Settings(BaseModel):
    # LLM
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "deepseek"))
    llm_api_key: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))

    # Redis
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/2"))

    # Database
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Server
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8900")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # Sandbox
    sandbox_timeout: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_TIMEOUT", "30")))
    sandbox_max_pages: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_MAX_PAGES", "10")))

    # Crawler
    default_concurrency: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_CONCURRENCY", "3")))
    default_delay: float = Field(default_factory=lambda: float(os.getenv("DEFAULT_DELAY", "1.0")))
    user_agent: str = Field(default_factory=lambda: os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ))


settings = Settings()
