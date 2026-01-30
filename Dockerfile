FROM --platform=$BUILDPLATFORM golang:1-alpine AS lprobe
ARG TARGETOS
ARG TARGETARCH
WORKDIR /build
ADD https://github.com/MShekow/local-health-check.git#main .
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o lprobe .

FROM dhi.io/python:3.14.2-dev AS build-stage

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m venv .venv
RUN python -m venv /tmp/poetry
COPY requirements-poetry.txt /tmp/
RUN /tmp/poetry/bin/pip install --no-cache-dir -r /tmp/requirements-poetry.txt
RUN /tmp/poetry/bin/poetry config virtualenvs.in-project true
COPY pyproject.toml poetry.lock ./
RUN /tmp/poetry/bin/poetry install --no-interaction --no-ansi --no-root --only main

COPY src/ ./src/

FROM alpine/curl:latest AS yq-downloader
# Download yq for fast YAML processing (used for Helm ChartMuseum index parsing)
# Note: TARGETARCH is e.g. arm64 or amd64
ARG TARGETARCH
# renovate-docker-env: datasource=github-tags depName=mikefarah/yq
ENV YQ_VERSION=v4.50.1
RUN curl -Lo /yq https://github.com/mikefarah/yq/releases/download/$YQ_VERSION/yq_linux_${TARGETARCH} \
  && chmod +x /yq


FROM dhi.io/python:3.14.2 AS runtime-stage

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

COPY --from=build-stage /app /app
COPY --from=yq-downloader /yq /usr/bin/yq

COPY --from=lprobe --link /build/lprobe /bin/lprobe
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD [ "lprobe", "-port=8000", "-endpoint=/health" ]

WORKDIR /app

EXPOSE 8000

ENTRYPOINT ["python", "/app/src/package_version_check_mcp/main.py"]
CMD ["--mode=http"]
