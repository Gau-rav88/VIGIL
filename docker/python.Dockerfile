FROM python:3.12-slim

ARG SERVICE_PATH=.

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    fonts-dejavu \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Copy workspace pyproject and packages
COPY pyproject.toml uv.lock* ./
COPY libs/ libs/
COPY services/ services/
COPY config/ config/
COPY migrations/ migrations/

RUN uv pip install --system -e libs/vigil_common

RUN if [ -f "${SERVICE_PATH}/pyproject.toml" ]; then \
        uv pip install --system -e "${SERVICE_PATH}"; \
    fi

WORKDIR /app

CMD ["python", "--version"]
