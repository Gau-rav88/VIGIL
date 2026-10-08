import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENV: Literal["dev", "prod", "test"] = "dev"
    LOG_LEVEL: str = "INFO"
    PUBLIC_BASE_URL: str = "http://localhost:3000"

    # Kafka / Redpanda
    KAFKA_BOOTSTRAP: str = "localhost:19092"
    KAFKA_ACKS: str = "1"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Timescale / Postgres
    PG_DSN: str = "postgresql://vigil:vigil@localhost:5432/vigil"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "vigilneo4j"

    # Object Store
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "vigil"
    S3_SECRET_KEY: str = "vigilvigil123"
    S3_REGION: str = "us-east-1"

    # Crypto
    SIGNER: Literal["file", "vault"] = "file"
    SIGNING_KEY_PATH: str = "keys/dev_ed25519.pem"
    SIGNING_KEY_ID: str = "dev-2026-01"
    PSEUDONYM_PEPPER: str = "change-me-dev-pepper-32bytes-min"
    TSA_URL: str | None = None

    # LLM
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "claude-sonnet-5-5"
    LLM_TIMEOUT_S: float = 2.0
    LLM_MAX_CONCURRENCY: int = 8
    LLM_TRACE_STORE_TEXT: bool = False

    # Market / Social Inputs
    MARKET_ADAPTER: str = "websocket"
    MARKET_WS_URL: str = "ws://localhost:8090/ws/market"
    SOCIAL_ADAPTER: str = "synthetic_ws"
    SOCIAL_WS_URL: str = "ws://localhost:8090/ws/social"
    INGEST_QUEUE_HIGH_WATERMARK: int = 50000

    # Agents
    ALIGN_INTERVAL_S: int = 5
    ALIGN_LOOKBACK_S: int = 3600
    ORCH_MAX_CONCURRENT_CASES: int = 8

    # Auth
    JWT_HS256_SECRET: str = "dev-secret-change-me"
    OIDC_ISSUER: str | None = None


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
