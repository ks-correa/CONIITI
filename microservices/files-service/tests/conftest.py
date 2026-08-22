import os
import tempfile

import pytest


_TEST_STORAGE = tempfile.TemporaryDirectory()
os.environ["FILES_DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_STORAGE.name, 'files-test.db')}"
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_STORAGE.name, "uploads")
os.environ["FILES_DATA_DIR"] = os.path.join(_TEST_STORAGE.name, "legacy")
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["INTERNAL_SERVICE_TOKEN"] = "test-internal-token"
os.environ["AUTH_SERVICE_URL"] = "http://auth-service.test"
os.environ["FILES_IMPORT_LEGACY_JSON"] = "false"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.clear()


def pytest_sessionfinish():
    engine.dispose()
    _TEST_STORAGE.cleanup()
