FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --gid 10001 atlas && useradd --uid 10001 --gid atlas --create-home atlas
COPY requirements.lock requirements-neural.lock pyproject.toml README.md ./
COPY src ./src
ARG INSTALL_NEURAL=false
RUN if [ "$INSTALL_NEURAL" = "true" ]; then pip install --require-hashes -r requirements-neural.lock; else pip install --require-hashes -r requirements.lock; fi \
    && pip install --no-deps .
COPY apps/api ./apps/api
COPY workers ./workers
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
COPY benchmarks ./benchmarks
COPY experiments ./experiments
COPY configs ./configs
RUN mkdir -p /app/data && chown -R atlas:atlas /app
USER atlas
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
