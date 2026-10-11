from __future__ import annotations

import pytest

from scripts.check_env import check_env


def test_env_check_passes_on_valid_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    env_vars = {
        "ENV": "dev",
        "KAFKA_BOOTSTRAP": "localhost:19092",
        "PG_DSN": "postgresql://vigil:vigil@localhost:5434/vigil",
        "REDIS_URL": "redis://localhost:6379/0",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "vigilneo4j",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_ACCESS_KEY": "vigil",
        "S3_SECRET_KEY": "vigilvigil123",
        "JWT_HS256_SECRET": "dev-secret-change-me",
        "PSEUDONYM_PEPPER": "change-me-dev-pepper-32bytes-min",
        "SIGNING_KEY_PATH": "keys/dev_ed25519.pem",
    }
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    assert check_env(load_file=False) == 0


def test_env_check_fails_on_missing_var(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Clear all required vars first
    for var in [
        "KAFKA_BOOTSTRAP", "PG_DSN", "REDIS_URL", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD",
        "S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "JWT_HS256_SECRET", "PSEUDONYM_PEPPER", "SIGNING_KEY_PATH"
    ]:
        monkeypatch.delenv(var, raising=False)

    code = check_env(load_file=False)
    assert code == 1
    captured = capsys.readouterr()
    assert "Missing required environment variable(s)" in captured.err
    assert "KAFKA_BOOTSTRAP" in captured.err


def test_env_check_refuses_prod_with_short_or_default_secrets(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    env_vars = {
        "ENV": "prod",
        "KAFKA_BOOTSTRAP": "prod-kafka:9092",
        "PG_DSN": "postgresql://user:pass@prod-db:5432/vigil",
        "REDIS_URL": "redis://prod-redis:6379/0",
        "NEO4J_URI": "bolt://prod-neo4j:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "vigilneo4j",  # default!
        "S3_ENDPOINT": "https://s3.amazonaws.com",
        "S3_ACCESS_KEY": "prod-key",
        "S3_SECRET_KEY": "vigilvigil123",  # default!
        "JWT_HS256_SECRET": "short-secret",  # < 32 chars!
        "PSEUDONYM_PEPPER": "short-pepper",  # < 32 chars!
        "SIGNING_KEY_PATH": "/secrets/prod_key.pem",
    }
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    code = check_env(load_file=False)
    assert code == 1
    captured = capsys.readouterr()
    assert "Production environment validation failed" in captured.err
    assert "JWT_HS256_SECRET must be at least 32 characters" in captured.err
    assert "insecure dev default" in captured.err
