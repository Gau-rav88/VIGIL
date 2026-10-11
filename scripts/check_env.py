#!/usr/bin/env python3
"""Environment variable validator for Project VIGIL.

Validates that all required configuration variables are present and secure.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

REQUIRED_VARS = [
    "KAFKA_BOOTSTRAP",
    "PG_DSN",
    "REDIS_URL",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "S3_ENDPOINT",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "JWT_HS256_SECRET",
    "PSEUDONYM_PEPPER",
    "SIGNING_KEY_PATH",
]

DEV_DEFAULT_SECRETS = {
    "JWT_HS256_SECRET": ["dev-secret-change-me", "dev-secret"],
    "PSEUDONYM_PEPPER": ["change-me-dev-pepper-32bytes-min"],
    "NEO4J_PASSWORD": ["vigilneo4j"],
    "S3_SECRET_KEY": ["vigilvigil123"],
}


def check_env(env_path: Path | None = None, load_file: bool = True) -> int:
    if load_file:
        env_file = env_path or Path(".env")
        if not env_file.exists():
            loaded_env_path = find_dotenv(usecwd=True)
            if loaded_env_path:
                load_dotenv(loaded_env_path)
        else:
            load_dotenv(env_file)

    missing: list[str] = []
    for var in REQUIRED_VARS:
        val = os.getenv(var)
        if val is None or val.strip() == "":
            missing.append(var)

    if missing:
        print(f"ERROR: Missing required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    env_mode = os.getenv("ENV", "dev").lower()
    if env_mode == "prod":
        errors: list[str] = []
        jwt_secret = os.getenv("JWT_HS256_SECRET", "")
        pepper = os.getenv("PSEUDONYM_PEPPER", "")

        if len(jwt_secret) < 32:
            errors.append("JWT_HS256_SECRET must be at least 32 characters in ENV=prod")
        if len(pepper) < 32:
            errors.append("PSEUDONYM_PEPPER must be at least 32 characters in ENV=prod")

        for secret_var, defaults in DEV_DEFAULT_SECRETS.items():
            current_val = os.getenv(secret_var, "")
            if any(current_val == d or d in current_val for d in defaults):
                errors.append(f"{secret_var} cannot use insecure dev default in ENV=prod")

        if errors:
            print("ERROR: Production environment validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

    print(f"Environment check passed (ENV={env_mode}).")
    return 0


if __name__ == "__main__":
    sys.exit(check_env())
