# syntax=docker/dockerfile:1.7

# Public, immutable Python base. The upstream SSC image requires registry
# credentials and cannot be used for reproducible external builds.
FROM python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111 AS base

USER root

RUN addgroup -S -g 65532 nonroot && \
    adduser -S -D -H -u 65532 -G nonroot nonroot

# Must pass the branch and commit as parameter
ARG branch
ARG commit
ARG version

ENV BRANCH=$branch
ENV COMMIT_HASH=$commit
ENV HOWLER_VERSION=$version

RUN mkdir -p /var/lib/howler && \
    mkdir -p /var/log/howler && \
    mkdir -p /var/cache/howler && \
    chmod 750 /var/lib/howler && \
    chmod 770 /var/log/howler && \
    chmod 770 /var/cache/howler && \
    chown nonroot:nonroot /var/lib/howler && \
    chown nonroot:nonroot /var/log/howler && \
    chown nonroot:nonroot /var/cache/howler && \
    chmod g+s /var/lib/howler

WORKDIR /var/lib/howler

RUN apk update && \
    apk add --no-cache tzdata && \
    rm -rf /var/cache/apk/*

USER nonroot

# ==========================================
# Builder Stage
# ==========================================
FROM base AS builder

USER root

RUN apk update && apk add --no-cache build-base gcc libffi-dev openssl-dev && rm -rf /var/cache/apk/*

ARG PIP_CERT=
ENV PIP_CERT=${PIP_CERT} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m pip install --no-cache-dir poetry

USER nonroot

ENV HOME=/var/lib/howler \
    XDG_CACHE_HOME=/var/cache/howler \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# Install only locked production dependencies before copying application code.
COPY --chown=nonroot:nonroot pyproject.toml poetry.lock ./

RUN --mount=type=cache,target=/var/cache/howler/pypoetry,uid=65532,gid=65532 \
    poetry install --only main --no-root --no-interaction --no-ansi

COPY --chown=nonroot:nonroot . .



FROM base

# Copy the constructed workspace and virtual environment over
COPY --chown=nonroot:nonroot --from=builder /var/lib/howler/ /var/lib/howler/

USER nonroot

ENV PATH=/var/lib/howler/.venv/bin:$PATH \
    HOME=/var/lib/howler \
    XDG_CACHE_HOME=/var/cache/howler \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/var/lib/howler

EXPOSE 8000

ENTRYPOINT ["python", "-m", "howler_mcp.server"]
