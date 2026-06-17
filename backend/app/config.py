from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    duckdb_path: str = "/data/taiex.duckdb"

    twse_openapi_base: str = "https://openapi.twse.com.tw/v1"
    twse_mis_base: str = "https://mis.twse.com.tw"
    yahoo_chart_base: str = "https://query1.finance.yahoo.com"

    twse_index_symbol: str = "tse_t00.tw"
    yahoo_index_symbol: str = "^TWII"

    market_open: str = "09:00"
    market_close: str = "13:30"
    tz_name: str = "Asia/Taipei"

    intraday_index_interval_sec: int = 30
    intraday_volume_interval_sec: int = 10

    daily_fetch_hour: int = 13
    daily_fetch_minute: int = 35

    http_timeout_sec: float = 15.0

    cors_origins: str = "*"


settings = Settings()
