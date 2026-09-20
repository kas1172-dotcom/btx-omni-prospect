import pytest

from btx_omni.persistence.seed_network_sample import assert_local_database


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_seed_accepts_only_local_postgresql(host):
    assert_local_database(f"postgresql+psycopg://user:masked@{host}:5432/test")


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://user:masked@database.example.com/test",
    "sqlite:///local.db",
    "postgresql+psycopg://user:masked@localhost/test?host=database.example.com",
    "postgresql+psycopg://user:masked@localhost/test?hostaddr=203.0.113.1",
    "postgresql+psycopg://user:masked@localhost/test?service=remote",
])
def test_seed_refuses_nonlocal_or_non_postgresql_database(url):
    with pytest.raises(ValueError, match="local PostgreSQL"):
        assert_local_database(url)
