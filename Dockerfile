FROM --platform=$BUILDPLATFORM golang:1-alpine AS lprobe
ARG TARGETOS
ARG TARGETARCH
WORKDIR /build
ADD https://github.com/MShekow/local-health-check.git#main .
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o lprobe .

# Temporarily use coarse 3.14 tag (instead of 3.14.x) while Renovate is not able to detect the latest tag from dhi.io
FROM dhi.io/python:3.14-dev AS build-stage

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

FROM alpine/curl:latest AS mise-downloader
# Download mise tool to determine various tool versions
# Note: TARGETARCH is e.g. arm64 or amd64
ARG TARGETARCH
# renovate-docker-env: datasource=github-tags depName=jdx/mise
ENV MISE_VERSION=v2026.1.12
RUN apk add --no-cache tar zstd && \
    MISE_ARCH=$([ "$TARGETARCH" = "amd64" ] && echo "x64" || echo "$TARGETARCH") && \
    curl -fsSL https://github.com/jdx/mise/releases/download/${MISE_VERSION}/mise-${MISE_VERSION}-linux-${MISE_ARCH}.tar.zst -o /tmp/mise.tar.zst && \
    tar -xf /tmp/mise.tar.zst -C /tmp && mv /tmp/mise/bin/mise /usr/bin/mise && \
    chmod +x /usr/bin/mise && rm -rf /tmp/mise.tar.zst /tmp/mise

# Temporarily use coarse 3.14 tag (instead of 3.14.x) while Renovate is not able to detect the latest tag from dhi.io
FROM dhi.io/python:3.14 AS runtime-stage

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

COPY --from=build-stage /app /app
COPY --from=mise-downloader /usr/bin/mise /usr/bin/mise

COPY --from=lprobe --link /build/lprobe /bin/lprobe
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD [ "lprobe", "-port=8000", "-endpoint=/health" ]

WORKDIR /app

EXPOSE 8000

ENTRYPOINT ["python", "/app/src/package_version_check_mcp/main.py"]
CMD ["--mode=http"]
