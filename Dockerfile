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

#copy migrations + alembic config so `alembic upgrade head` can run in the image
COPY migrations/ ./migrations/
COPY alembic.ini ./

#entrypoint runs migrations before handing off to CMD (or a compose override)
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
