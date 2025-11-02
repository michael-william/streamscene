"""Pytest configuration and fixtures for StreamScene tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from streamscene.core.database import Base
from streamscene.core import models  # Import to register models


# Use in-memory SQLite for tests (fast and isolated)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def session(engine) -> Session:
    """Create a test database session."""
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(session) -> models.User:
    """Create a sample user for testing."""
    user = models.User(authentik_user_id="test-user-123")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def sample_user2(session) -> models.User:
    """Create a second sample user for testing."""
    user = models.User(authentik_user_id="test-user-456")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def sample_stream(session, sample_user) -> models.Stream:
    """Create a sample stream for testing."""
    stream = models.Stream(
        owner_id=sample_user.id,
        name="Test Stream",
        description="A test stream",
        is_public=False,
        allow_text=True,
        allow_images=False,
    )
    session.add(stream)
    session.commit()
    session.refresh(stream)
    return stream


@pytest.fixture
def sample_post(session, sample_stream, sample_user) -> models.Post:
    """Create a sample post for testing."""
    post = models.Post(
        stream_id=sample_stream.id,
        author_id=sample_user.id,
        content_type="text",
        text_content="This is a test post",
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return post
