FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS construcao
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /construcao
COPY requirements.txt .
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt \
    && python -m pip install --no-cache-dir --no-index --no-deps --no-compile --target=/install /wheels/*

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/runtime
WORKDIR /app
COPY --from=construcao /install /opt/runtime
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --chown=10001:10001 vigia/ ./vigia/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["python", "-m", "uvicorn", "vigia.main:criar_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
