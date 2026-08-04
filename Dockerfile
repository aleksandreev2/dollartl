FROM node:22-alpine AS admin-builder
WORKDIR /admin
ARG VITE_ADMIN_DEVELOPMENT_ID=""
ENV VITE_ADMIN_DEVELOPMENT_ID=${VITE_ADMIN_DEVELOPMENT_ID}
COPY admin-web/package.json admin-web/tsconfig.json admin-web/vite.config.ts admin-web/index.html ./
COPY admin-web/src ./src
RUN npm install --no-audit --no-fund && npm run build

FROM python:3.13-slim AS python-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip && python -m pip wheel --wheel-dir /wheels .

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ADMIN_WEB_DIR=/app/admin-web-dist
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=python-builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --from=admin-builder /admin/dist ./admin-web-dist
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
RUN chmod +x scripts/*.sh
USER 65532:65532
CMD ["uvicorn", "dollartl.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
