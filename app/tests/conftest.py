import os
import pytest

from main import app as flask_app
from db import db


@pytest.fixture(scope="session", autouse=True)
def _env():
    os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    os.environ["APP_SECRET_KEY"] = "test-secret"


@pytest.fixture(scope="session")
def app():
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        db.create_all()
    yield flask_app
    with flask_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
