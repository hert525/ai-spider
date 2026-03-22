"""Core configuration."""
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent.parent


class Settings(BaseModel):
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "deepseek"))
    llm_api_key: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))

    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/2"))

    db_path: str = Field(default_factory=lambda: os.getenv("DB_PATH", str(BASE_DIR / "data" / "spider.db")))

    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8900")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    sandbox_timeout: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_TIMEOUT", "30")))
    sandbox_max_pages: int = Field(default_factory=lambda: int(os.getenv("SANDBOX_MAX_PAGES", "10")))
    default_concurrency: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_CONCURRENCY", "3")))
    default_delay: float = Field(default_factory=lambda: float(os.getenv("DEFAULT_DELAY", "1.0")))
    user_agent: str = Field(default_factory=lambda: os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ))
    default_proxy: str = Field(default_factory=lambda: os.getenv("DEFAULT_PROXY", ""))

    # === 从 wukong 移植的增强配置 ===

    # 限速配置
    rate_limit_enabled: bool = Field(
        default_factory=lambda: os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
    )
    global_qps: int = Field(default_factory=lambda: int(os.getenv("GLOBAL_QPS", "100")))

    # 去重配置
    dedup_strategy: str = Field(default_factory=lambda: os.getenv("DEDUP_STRATEGY", "memory"))
    dedup_capacity: int = Field(default_factory=lambda: int(os.getenv("DEDUP_CAPACITY", "1000000")))

    # 监控配置
    metrics_enabled: bool = Field(
        default_factory=lambda: os.getenv("METRICS_ENABLED", "false").lower() == "true"
    )
    pushgateway_url: str = Field(default_factory=lambda: os.getenv("PUSHGATEWAY_URL", "http://localhost:9091"))

    # 火山引擎代理
    volcano_http_endpoint: str = Field(default_factory=lambda: os.getenv("VOL_HTTP_ENDPOINT", ""))
    volcano_https_endpoint: str = Field(default_factory=lambda: os.getenv("VOL_HTTPS_ENDPOINT", ""))

    # 存储配置
    parquet_output_dir: str = Field(default_factory=lambda: os.getenv("PARQUET_OUTPUT_DIR", "data/parquet_output"))
    parquet_compression: str = Field(default_factory=lambda: os.getenv("PARQUET_COMPRESSION", "zstd"))

    @property
    def llm_model_string(self) -> str:
        """返回带provider前缀的模型名（供litellm使用）"""
        model = self.llm_model
        if self.llm_provider and "/" not in model:
            model = f"{self.llm_provider}/{model}"
        return model

    def get_llm_model(self) -> str:
        """Return model string with provider prefix for litellm."""
        return self.llm_model_string

    def get_llm_params(self) -> dict:
        """Build LiteLLM completion params."""
        params = {"model": self.get_llm_model(), "api_key": self.llm_api_key}
        if self.llm_base_url:
            params["api_base"] = self.llm_base_url
        elif self.llm_provider == "deepseek":
            params["api_base"] = "https://api.deepseek.com/v1"
        return params


settings = Settings()
