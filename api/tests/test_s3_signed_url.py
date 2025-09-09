"""Tests for the `/s3/signed-url` endpoint.

This test-suite verifies:
1. Regular users can retrieve signed URLs for resources belonging to their own workflow runs.
2. Regular users are *forbidden* from accessing resources that belong to other users.
3. Superusers can access any resource irrespective of ownership.
"""

import os
from unittest.mock import AsyncMock

import pytest
from fastapi import status

# Ensure the S3 environment variables exist so that the module import does not fail
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("S3_REGION", "us-east-1")


@pytest.mark.asyncio
async def test_signed_url_for_own_run(monkeypatch, test_client_factory, db_session):
    """A normal user should be able to fetch a signed URL for their own workflow run."""
    from api.db.models import UserModel

    # ------------------------------------------------------------------
    # 1. Set-up – create user, workflow & workflow run
    # ------------------------------------------------------------------
    user: UserModel = await db_session.get_or_create_user_by_provider_id("user_own_run")
    workflow = await db_session.create_workflow("wf", {}, user.id)
    run = await db_session.create_workflow_run("run", workflow.id, "chat", user.id)

    key = f"transcripts/{run.id}.txt"

    # Patch S3 signed-url generator to avoid network calls
    monkeypatch.setattr(
        "api.services.filesystem.s3.s3_fs.aget_signed_url",
        AsyncMock(return_value="https://signed-url"),
    )

    async with test_client_factory(user) as client:
        response = await client.get(f"/api/v1/s3/signed-url?key={key}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == {"url": "https://signed-url", "expires_in": 3600}


@pytest.mark.asyncio
async def test_signed_url_for_other_users_run_forbidden(
    monkeypatch, test_client_factory, db_session
):
    """A normal user must *not* access workflow runs owned by someone else."""
    from api.db.models import UserModel

    # Owner of the workflow run
    owner: UserModel = await db_session.get_or_create_user_by_provider_id("owner_user")
    workflow = await db_session.create_workflow("wf", {}, owner.id)
    run = await db_session.create_workflow_run("run", workflow.id, "chat", owner.id)

    # Second user attempting access
    intruder: UserModel = await db_session.get_or_create_user_by_provider_id(
        "intruder_user"
    )

    key = f"recordings/{run.id}.wav"

    monkeypatch.setattr(
        "api.services.filesystem.s3.s3_fs.aget_signed_url",
        AsyncMock(return_value="https://signed-url"),
    )

    async with test_client_factory(intruder) as client:
        response = await client.get(f"/api/v1/s3/signed-url?key={key}")

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_superuser_can_access_any_run(
    monkeypatch, test_client_factory, db_session
):
    """Superusers should be able to fetch signed URLs for any workflow run."""
    from api.db.models import UserModel

    # Normal user & run owner
    owner: UserModel = await db_session.get_or_create_user_by_provider_id(
        "owner_of_run"
    )
    workflow = await db_session.create_workflow("wf", {}, owner.id)
    run = await db_session.create_workflow_run("run", workflow.id, "chat", owner.id)

    # Superuser
    superuser: UserModel = await db_session.get_or_create_user_by_provider_id(
        "admin_user"
    )

    # Promote to superuser
    # We need to commit the change so that the DB reflects it
    async with db_session.async_session() as session:
        db_user = await session.get(UserModel, superuser.id)
        db_user.is_superuser = True
        await session.commit()
        await session.refresh(db_user)  # ensure we have the latest state
        superuser.is_superuser = True

    key = f"transcripts/{run.id}.txt"

    monkeypatch.setattr(
        "api.services.filesystem.s3.s3_fs.aget_signed_url",
        AsyncMock(return_value="https://signed-url"),
    )

    async with test_client_factory(superuser) as client:
        response = await client.get(f"/api/v1/s3/signed-url?key={key}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["url"] == "https://signed-url"
