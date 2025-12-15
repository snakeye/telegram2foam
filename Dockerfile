FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/app/.venv

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates openssh-client curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv and sync dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "python", "main.py"]
