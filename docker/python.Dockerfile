FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    fonts-dejavu \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY libs/ libs/
COPY services/ services/
COPY config/ config/
COPY migrations/ migrations/
COPY infra/ infra/
COPY scripts/ scripts/
COPY keys/ keys/

RUN uv sync --all-packages

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["python", "--version"]
