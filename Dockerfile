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
RUN /tmp/poetry/bin/poetry install --no-interaction --no-ansi --no-root

COPY src/ ./src/

FROM dhi.io/python:3.14.2 AS runtime-stage

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# TODO chown root
COPY --from=build-stage /app /app

WORKDIR /app

EXPOSE 8000

CMD ["python", "/app/src/package_version_check_mcp/main.py"]
