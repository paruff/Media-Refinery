import pytest

try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer
    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None
    RedisContainer = None


if TESTCONTAINERS_AVAILABLE:
    @pytest.fixture(scope="session")
    def postgres_container():
        """
        Spins up a real ephemeral Postgres instance for integration tests.
        """
        with PostgresContainer("postgres:15-alpine") as postgres:
            yield {
                "host": postgres.get_container_host_ip(),
                "port": postgres.get_exposed_port(5432),
                "user": postgres.USER,
                "password": postgres.PASSWORD,
                "database": postgres.DB,
                "dsn": postgres.get_connection_url(),
            }


    @pytest.fixture(scope="session")
    def redis_container():
        """
        Spins up a real ephemeral Redis instance for integration tests.
        """
        with RedisContainer("redis:7-alpine") as redis:
            yield {
                "host": redis.get_container_host_ip(),
                "port": redis.get_exposed_port(6379),
            }


@pytest.fixture
def dummy_media_file(tmp_path):
    """
    Creates a minimal valid MKV or FLAC file for scanner tests.
    Returns the file path.
    """
    mkv_header = b"\x1A\x45\xDF\xA3"  # EBML header for MKV
    flac_header = b"fLaC"  # FLAC header
    mkv_path = tmp_path / "dummy.mkv"
    flac_path = tmp_path / "dummy.flac"
    mkv_path.write_bytes(mkv_header + b"\x00" * 128)
    flac_path.write_bytes(flac_header + b"\x00" * 128)
    return {"mkv": str(mkv_path), "flac": str(flac_path)}
