"""
Shared pytest fixtures for the API tests.
This file contains database setup, test client configuration, and utility fixtures
that can be reused across all test files.
"""

import os
import subprocess
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.app import app
from api.db import db_client

# Test database setup globals
TEST_DATABASE_NAME = None
TEST_DATABASE_URL = None


@pytest_asyncio.fixture
async def test_database():
    """
    Set up a temporary PostgreSQL database for testing.
    This fixture creates a unique test database, runs migrations, and cleans up afterward.
    """
    global TEST_DATABASE_NAME, TEST_DATABASE_URL

    # Generate a unique test database name
    TEST_DATABASE_NAME = f"test_dograh_{uuid.uuid4().hex[:8]}"

    # Get the base DATABASE_URL and parse it
    base_url = os.environ.get("DATABASE_URL")
    # Extract connection parts and replace database name
    url_parts = base_url.split("/")
    base_connection = "/".join(url_parts[:-1])
    TEST_DATABASE_URL = f"{base_connection}/{TEST_DATABASE_NAME}"

    # Create a connection to the default postgres database to create our test database
    default_engine = create_async_engine(base_url)

    try:
        # Create the test database
        async with default_engine.connect() as conn:
            # Use autocommit mode to create database
            await conn.execute(text("COMMIT"))
            await conn.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))

        await default_engine.dispose()

        # Run migrations on the test database
        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL
        # Add the parent directory to PYTHONPATH so alembic can find the api module
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = parent_dir + ":" + env.get("PYTHONPATH", "")

        # Run alembic upgrade to create all tables
        result = subprocess.run(
            [
                "conda",
                "run",
                "-n",
                "dograh",
                "python",
                "-m",
                "alembic",
                "-c",
                "alembic.ini",
                "upgrade",
                "head",
            ],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Alembic stderr: {result.stderr}")
            logger.error(f"Alembic stdout: {result.stdout}")
            raise RuntimeError(f"Alembic migration failed: {result.stderr}")

        logger.info(f"Created test database: {TEST_DATABASE_NAME}")
        yield TEST_DATABASE_URL

    finally:
        # Cleanup: Drop the test database
        cleanup_engine = create_async_engine(base_url)
        try:
            async with cleanup_engine.connect() as conn:
                # Terminate any connections to the test database
                await conn.execute(text("COMMIT"))
                await conn.execute(
                    text(f"""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = '{TEST_DATABASE_NAME}' AND pid <> pg_backend_pid()
                """)
                )
                await conn.execute(
                    text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME}")
                )
            logger.info(f"Cleaned up test database: {TEST_DATABASE_NAME}")
        except Exception as e:
            logger.error(
                f"Warning: Could not clean up test database {TEST_DATABASE_NAME}: {e}"
            )
        finally:
            await cleanup_engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_database):
    """
    Create a test database client that uses the temporary database.
    This fixture replaces the global db_client with a test version.
    """
    original_engine = db_client.engine
    original_session = db_client.async_session

    # Replace the database client's engine and session with test ones
    test_engine = create_async_engine(test_database)
    test_session_maker = async_sessionmaker(bind=test_engine)

    db_client.engine = test_engine
    db_client.async_session = test_session_maker

    yield db_client

    # Restore original database client
    await test_engine.dispose()
    db_client.engine = original_engine
    db_client.async_session = original_session


@pytest_asyncio.fixture
async def test_client_factory(db_session):
    """
    Factory fixture that creates test clients for specific users.
    This allows tests to create custom users and test clients on demand.

    Usage:
        async def test_something(test_client_factory, db_session):
            # Create a custom user
            user = await db_session.get_or_create_user_by_provider_id("custom_user_123")

            # Create a test client for this user
            async with test_client_factory(user) as client:
                # Use the client in your test
                response = await client.get("/some/endpoint")
    """
    from contextlib import asynccontextmanager

    from api.services.auth.depends import get_user

    @asynccontextmanager
    async def _create_client_for_user(user):
        # Create mock auth dependency for this user
        async def mock_get_user():
            return user

        # Override the dependency
        original_override = app.dependency_overrides.get(get_user)
        app.dependency_overrides[get_user] = mock_get_user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client
        finally:
            # Clean up the override
            if original_override:
                app.dependency_overrides[get_user] = original_override
            else:
                app.dependency_overrides.pop(get_user, None)

    return _create_client_for_user
