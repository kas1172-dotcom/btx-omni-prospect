FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.23 /uv /uvx /bin/
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
COPY backend/src ./src
COPY docs/research /docs/research
RUN uv sync --frozen --no-dev
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./

# Inject only public identifiers from the reviewed, clean release checkout.
# Empty/unknown defaults remain visibly unverified; a liveness check is not proof.
ARG BTX_RELEASE_SHA=""
ARG BTX_RELEASE_TREE=""
ARG BTX_RELEASE_WORKTREE="unknown"
ENV BTX_RELEASE_SHA=$BTX_RELEASE_SHA BTX_RELEASE_TREE=$BTX_RELEASE_TREE BTX_RELEASE_WORKTREE=$BTX_RELEASE_WORKTREE

EXPOSE 8080
CMD ["uv", "run", "--no-sync", "uvicorn", "btx_omni.app:app", "--host", "0.0.0.0", "--port", "8080"]
