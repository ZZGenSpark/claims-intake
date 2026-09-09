# Runtime image for the claims intake service.
# Build from this directory:
#   docker buildx build --platform linux/amd64 -t claims-intake .

# ---- build stage: resolve and install dependencies into a virtualenv ----
FROM python:3.12-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# uv sync installs the project editable, so claims.policy_client resolves
# data/policies.json as parents[2] / data (i.e. /app/data), not site-packages.
# The source and data must be present when the venv is built.
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY data ./data

RUN uv sync --frozen --no-dev

# ---- runtime stage: carry only the app and its venv, no build tooling ----
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

# /app holds the venv (editable link to /app/src), the source, and the data.
COPY --from=build /app /app

# Run as an unprivileged user.
RUN useradd --system --no-create-home claims
USER claims

EXPOSE 8000

CMD ["uvicorn", "claims.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
