#base image
FROM python:3.12-slim
#workdir
WORKDIR /app

#copy the official uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

#copy project root with pyproject.toml and uv.lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

#copy the full backend/app structure
COPY backend/ ./backend/
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
