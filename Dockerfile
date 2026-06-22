FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system geoflood && useradd --system --gid geoflood geoflood

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip && python -m pip install .

RUN mkdir -p /data /app/outputs && chown -R geoflood:geoflood /data /app/outputs

USER geoflood

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "geoflood.api:app", "--host", "0.0.0.0", "--port", "8000"]
