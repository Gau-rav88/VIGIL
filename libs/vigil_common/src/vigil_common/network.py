from __future__ import annotations

import os
import socket


def resolve_kafka_bootstrap(bootstrap: str | None = None) -> str:
    """Resolve Kafka/Redpanda bootstrap server.

    If bootstrap points to the Docker service name 'redpanda' but the service name
    cannot be resolved (i.e. running on the host machine outside Docker), falls back
    to localhost:19092.
    """
    raw = bootstrap or os.getenv("KAFKA_BOOTSTRAP") or "redpanda:9092"
    host, _, _ = raw.partition(":")
    if host == "redpanda":
        try:
            socket.gethostbyname("redpanda")
        except socket.gaierror:
            ext_port = os.getenv("KAFKA_EXTERNAL_PORT", "19092")
            return f"localhost:{ext_port}"
    return raw


def resolve_db_dsn(dsn: str | None = None) -> str:
    """Resolve Timescale/Postgres DSN.

    If the DSN points to the Docker service name 'timescale' but cannot be resolved,
    falls back to localhost:5434.
    """
    raw = (
        dsn
        or os.getenv("TIMESCALE_DSN")
        or os.getenv("PG_DSN")
        or "postgresql://vigil:vigil@timescale:5432/vigil"
    )
    if "@timescale:5432" in raw:
        try:
            socket.gethostbyname("timescale")
        except socket.gaierror:
            ext_port = os.getenv("PG_EXTERNAL_PORT", "5434")
            return raw.replace("@timescale:5432", f"@localhost:{ext_port}")
    return raw


def resolve_redis_url(url: str | None = None) -> str:
    """Resolve Redis URL.

    If the URL points to the Docker service name 'redis' but cannot be resolved,
    falls back to localhost:6379.
    """
    raw = url or os.getenv("REDIS_URL") or "redis://redis:6379/0"
    if "redis:6379" in raw:
        try:
            socket.gethostbyname("redis")
        except socket.gaierror:
            return raw.replace("redis:6379", "localhost:6379")
    return raw


def resolve_neo4j_uri(uri: str | None = None) -> str:
    """Resolve Neo4j URI.

    If the URI points to local Docker service name 'neo4j' but cannot be resolved,
    falls back to localhost:7687.
    """
    raw = uri or os.getenv("NEO4J_URI") or "bolt://neo4j:7687"
    if "://neo4j:7687" in raw:
        try:
            socket.gethostbyname("neo4j")
        except socket.gaierror:
            return raw.replace("://neo4j:7687", "://localhost:7687")
    return raw


def resolve_s3_endpoint(endpoint: str | None = None) -> str:
    """Resolve MinIO/S3 endpoint URL.

    If the endpoint points to Docker service name 'minio' but cannot be resolved,
    falls back to localhost:9000.
    """
    raw = endpoint or os.getenv("S3_ENDPOINT") or "http://minio:9000"
    if "minio:9000" in raw:
        try:
            socket.gethostbyname("minio")
        except socket.gaierror:
            return raw.replace("minio:9000", "localhost:9000")
    return raw
