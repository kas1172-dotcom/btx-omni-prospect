from pathlib import Path


def test_backend_ci_migrates_before_pytest_and_validates_openapi_last() -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    ).read_text()
    install = workflow.index("uv sync --frozen --all-groups")
    ruff = workflow.index("uv run ruff check .")
    upgrade = workflow.index("uv run alembic upgrade head")
    current = workflow.index("uv run alembic current")
    pytest = workflow.index("uv run pytest")
    openapi = workflow.index("schema = app.openapi()")
    assert install < ruff < upgrade < current < pytest < openapi
