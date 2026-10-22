"""Environment-driven configuration for Worker B (persistence)."""
from __future__ import annotations
from asyncio.log import logger
from sqlalchemy.engine import URL
from urllib.parse import quote_plus
import os


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


class Settings:
    # --- Redis ---
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost") 
    REDIS_PORT: int = _get_int("REDIS_PORT", 6379)
    REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD") or "RobCompPCPass"
    REDIS_CHANNEL: str = os.getenv("REDIS_CHANNEL", "RobComp-PC") 

    # --- MySQL ---
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT: int = _get_int("MYSQL_PORT", 3306)
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "RobComp-PC")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "RobComp-PC")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "RobCompPCPass") 
    
    FASTAPI_API_KEY: str = os.environ.get("FASTAPI_API_KEY", "default-key") 
    FASTAPI_API_KEY_HEADER: str = os.getenv("FASTAPI_API_KEY_HEADER", "X-API-Key")

    # --- Batching / persistence ---
    BATCH_SIZE: int = _get_int("WORKER_B_BATCH_SIZE", 200)
    FLUSH_INTERVAL: float = float(os.getenv("WORKER_B_FLUSH_INTERVAL", "1.0"))

    # --- Resilience ---
    RECONNECT_MAX_DELAY: float = float(os.getenv("WORKER_B_RECONNECT_MAX_DELAY", "30.0"))

    @property
    def redis_url(self) -> str:
        auth = f":{quote_plus(self.REDIS_PASSWORD)}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def mysql_url(self) -> str:
        return URL.create(
            drivername="mysql+aiomysql",
            username=self.MYSQL_USER,
            password=self.MYSQL_PASSWORD,
            host=self.MYSQL_HOST,
            port=self.MYSQL_PORT,
            database=self.MYSQL_DATABASE,
            query={"charset": "utf8mb4"}
        ).render_as_string(hide_password=False)


settings = Settings()