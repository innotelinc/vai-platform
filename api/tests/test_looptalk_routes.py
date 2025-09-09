"""
Tests for LoopTalk API routes and orchestration.

This module tests the LoopTalk testing functionality including test session creation,
pipeline orchestration, and agent-to-agent communication.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status

from api.db.db_client import DBClient
from api.services.looptalk.orchestrator import LoopTalkTestOrchestrator


@pytest.fixture
def actor_workflow_definition():
    """Sample actor workflow definition for testing."""
    return {
        "nodes": [
            {
                "id": "1",
                "type": "startCall",
                "position": {"x": 0, "y": 0},
                "data": {
                    "prompt": "Hello, I'm the actor agent.",
                    "is_static": True,
                    "name": "Start Call",
                    "is_start": True,
                    "allow_interrupt": False,
                },
            },
            {
                "id": "2",
                "type": "agentNode",
                "position": {"x": 100, "y": 0},
                "data": {
                    "prompt": "You are an actor agent testing the adversary. Ask probing questions.",
                    "name": "Actor Agent",
                    "allow_interrupt": True,
                },
            },
            {
                "id": "3",
                "type": "endCall",
                "position": {"x": 200, "y": 0},
                "data": {
                    "prompt": "Goodbye!",
                    "name": "End Call",
                    "is_end": True,
                },
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "1",
                "target": "2",
                "data": {"label": "Continue", "condition": "Always"},
            },
            {
                "id": "e2",
                "source": "2",
                "target": "3",
                "data": {"label": "End", "condition": "Always"},
            },
        ],
        "stt": {"provider": "openai", "api_key": "test-key", "model": "whisper-1"},
        "llm": {"provider": "openai", "api_key": "test-key", "model": "gpt-4o-mini"},
        "tts": {
            "provider": "openai",
            "api_key": "test-key",
            "model": "tts-1",
            "voice": "nova",
        },
    }


@pytest.fixture
def adversary_workflow_definition():
    """Sample adversary workflow definition for testing."""
    return {
        "nodes": [
            {
                "id": "1",
                "type": "startCall",
                "position": {"x": 0, "y": 0},
                "data": {
                    "prompt": "Hello, I'm the adversary agent.",
                    "is_static": True,
                    "name": "Start Call",
                    "is_start": True,
                    "allow_interrupt": False,
                },
            },
            {
                "id": "2",
                "type": "agentNode",
                "position": {"x": 100, "y": 0},
                "data": {
                    "prompt": "You are an adversary agent being tested. Respond defensively.",
                    "name": "Adversary Agent",
                    "allow_interrupt": True,
                },
            },
            {
                "id": "3",
                "type": "endCall",
                "position": {"x": 200, "y": 0},
                "data": {
                    "prompt": "Goodbye!",
                    "name": "End Call",
                    "is_end": True,
                },
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "1",
                "target": "2",
                "data": {"label": "Continue", "condition": "Always"},
            },
            {
                "id": "e2",
                "source": "2",
                "target": "3",
                "data": {"label": "End", "condition": "Always"},
            },
        ],
        "stt": {"provider": "deepgram", "api_key": "test-key", "model": "nova-2"},
        "llm": {
            "provider": "groq",
            "api_key": "test-key",
            "model": "llama-3.1-70b-versatile",
        },
        "tts": {"provider": "deepgram", "api_key": "test-key", "voice": "nova-2"},
    }


from pipecat.processors.frame_processor import FrameProcessor


class MockSTTService(FrameProcessor):
    """Mock STT service for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def run_stt(self, audio: bytes) -> str:
        return "Mock transcription"


class MockLLMService(FrameProcessor):
    """Mock LLM service for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def run_llm(self, messages) -> str:
        return "Mock LLM response"

    def create_context_aggregator(self, context):
        """Mock context aggregator creation."""
        return MagicMock()


class MockTTSService(FrameProcessor):
    """Mock TTS service for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def run_tts(self, text: str) -> bytes:
        return b"Mock audio data"


@pytest_asyncio.fixture
async def test_user_with_org(db_session):
    """Create a test user with an organization set up."""
    user = await db_session.get_or_create_user_by_provider_id("test_looptalk_user")
    org, _ = await db_session.get_or_create_organization_by_provider_id(
        "test_looptalk_org"
    )

    user_id = user.id
    org_id = org.id

    await db_session.add_user_to_organization(user_id, org_id)

    # Update user's selected organization
    async with db_session.async_session() as session:
        from sqlalchemy import update

        from api.db.models import UserModel

        await session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(selected_organization_id=org_id)
        )
        await session.commit()

    # Return fresh user object
    return await db_session.get_user_by_id(user_id)


@pytest.mark.asyncio
async def test_create_test_session(
    test_client_factory,
    db_session,
    test_user_with_org,
    actor_workflow_definition,
    adversary_workflow_definition,
):
    """Test creating a new LoopTalk test session."""
    async with test_client_factory(test_user_with_org) as test_client:
        # First create two workflows
        actor_workflow_response = await test_client.post(
            "/api/v1/workflow/create",
            json={
                "name": "Actor Workflow",
                "workflow_definition": actor_workflow_definition,
            },
        )
        assert actor_workflow_response.status_code == status.HTTP_200_OK
        actor_workflow_id = actor_workflow_response.json()["id"]

        adversary_workflow_response = await test_client.post(
            "/api/v1/workflow/create",
            json={
                "name": "Adversary Workflow",
                "workflow_definition": adversary_workflow_definition,
            },
        )
        assert adversary_workflow_response.status_code == status.HTTP_200_OK
        adversary_workflow_id = adversary_workflow_response.json()["id"]

        # Create test session
        response = await test_client.post(
            "/api/v1/looptalk/test-sessions",
            json={
                "name": "Test Session 1",
                "actor_workflow_id": actor_workflow_id,
                "adversary_workflow_id": adversary_workflow_id,
                "config": {"test_duration": 60},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Test Session 1"
        assert data["status"] == "pending"
        assert data["actor_workflow_id"] == actor_workflow_id
        assert data["adversary_workflow_id"] == adversary_workflow_id
        assert data["config"]["test_duration"] == 60


@pytest.mark.asyncio
async def test_list_test_sessions(test_client_factory, db_session, test_user_with_org):
    """Test listing LoopTalk test sessions."""
    async with test_client_factory(test_user_with_org) as test_client:
        response = await test_client.get(
            "/api/v1/looptalk/test-sessions",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_looptalk_orchestrator_plumbing(
    db_session: DBClient, actor_workflow_definition, adversary_workflow_definition
):
    """Test the LoopTalk orchestrator plumbing with mocked services."""

    # Create test user and organization
    user = await db_session.get_or_create_user_by_provider_id(
        provider_id="test-user-123"
    )
    org, _ = await db_session.get_or_create_organization_by_provider_id(
        org_provider_id="test-org-123"
    )

    # Get IDs before session closes
    user_id = user.id
    org_id = org.id

    await db_session.add_user_to_organization(user_id, org_id)

    # Update user's selected organization manually
    async with db_session.async_session() as session:
        from sqlalchemy import update

        from api.db.models import UserModel

        await session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(selected_organization_id=org_id)
        )
        await session.commit()

    actor_workflow = await db_session.create_workflow(
        name="Actor Workflow",
        workflow_definition=actor_workflow_definition,
        user_id=user_id,
    )

    adversary_workflow = await db_session.create_workflow(
        name="Adversary Workflow",
        workflow_definition=adversary_workflow_definition,
        user_id=user_id,
    )

    # Create test session
    test_session = await db_session.create_test_session(
        organization_id=org_id,
        name="Test Session",
        actor_workflow_id=actor_workflow.id,
        adversary_workflow_id=adversary_workflow.id,
        config={"test_duration": 10},
    )

    # Mock the service factories - patch at the actual import location in pipeline_builder
    with (
        patch(
            "api.services.looptalk.core.pipeline_builder.create_stt_service"
        ) as mock_stt_factory,
        patch(
            "api.services.looptalk.core.pipeline_builder.create_llm_service"
        ) as mock_llm_factory,
        patch(
            "api.services.looptalk.core.pipeline_builder.create_tts_service"
        ) as mock_tts_factory,
        patch(
            "api.services.workflow.pipecat_engine.PipecatEngine"
        ) as mock_engine_class,
        patch(
            "api.services.pipecat.pipeline_builder.build_pipeline"
        ) as mock_build_pipeline,
        patch("api.services.pipecat.pipeline_builder.PipelineTask") as mock_task_class,
    ):
        # Configure mocks
        mock_stt_factory.return_value = MockSTTService()
        mock_llm_factory.return_value = MockLLMService()
        mock_tts_factory.return_value = MockTTSService()

        mock_engine = MagicMock()
        mock_engine.initialize = AsyncMock()
        mock_engine.get_callback_processor = MagicMock(return_value=MagicMock())
        mock_engine_class.return_value = mock_engine

        # Mock pipeline and task
        mock_pipeline = MagicMock()
        mock_task = MagicMock()
        mock_task.run = AsyncMock()
        mock_task.cancel = AsyncMock()  # Make cancel async
        mock_build_pipeline.return_value = mock_pipeline
        mock_task_class.return_value = mock_task

        # Create orchestrator
        orchestrator = LoopTalkTestOrchestrator(db_client=db_session)

        # Start test session (in a separate task to avoid blocking)
        start_task = asyncio.create_task(
            orchestrator.start_test_session(
                test_session_id=test_session.id, organization_id=org_id
            )
        )

        # Give it a moment to start
        await asyncio.sleep(0.5)

        # Verify the session is running through session manager
        session_info = orchestrator.session_manager.get_session(test_session.id)
        assert session_info is not None
        assert session_info["test_session"].id == test_session.id
        assert "actor_task" in session_info
        assert "adversary_task" in session_info

        # Verify service factories were called
        assert mock_stt_factory.call_count == 2  # Once for each agent
        assert mock_llm_factory.call_count == 2
        assert mock_tts_factory.call_count == 2

        # Verify pipelines were created with PipelineTask
        assert mock_task_class.call_count == 2

        # Stop the test session
        await orchestrator.stop_test_session(test_session_id=test_session.id)

        # Verify session was cleaned up
        assert orchestrator.session_manager.get_session(test_session.id) is None

        # Cancel the start task
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_load_test_creation(
    test_client_factory,
    db_session,
    test_user_with_org,
    actor_workflow_definition,
    adversary_workflow_definition,
):
    """Test creating a load test with multiple sessions."""
    async with test_client_factory(test_user_with_org) as test_client:
        # First create two workflows
        actor_workflow_response = await test_client.post(
            "/api/v1/workflow/create",
            json={
                "name": "Actor Workflow",
                "workflow_definition": actor_workflow_definition,
            },
        )
        actor_workflow_id = actor_workflow_response.json()["id"]

        adversary_workflow_response = await test_client.post(
            "/api/v1/workflow/create",
            json={
                "name": "Adversary Workflow",
                "workflow_definition": adversary_workflow_definition,
            },
        )
        adversary_workflow_id = adversary_workflow_response.json()["id"]

        # Create load test
        response = await test_client.post(
            "/api/v1/looptalk/load-tests",
            json={
                "name_prefix": "Load Test",
                "actor_workflow_id": actor_workflow_id,
                "adversary_workflow_id": adversary_workflow_id,
                "test_count": 3,
                "config": {"test_duration": 30},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
        assert "load_test_group_id" in data
        assert len(data["test_session_ids"]) == 3


@pytest.mark.asyncio
async def test_invalid_workflow_ids(
    test_client_factory, db_session, test_user_with_org
):
    """Test creating test session with invalid workflow IDs."""
    async with test_client_factory(test_user_with_org) as test_client:
        response = await test_client.post(
            "/api/v1/looptalk/test-sessions",
            json={
                "name": "Invalid Test",
                "actor_workflow_id": 99999,
                "adversary_workflow_id": 99999,
                "config": {},
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "workflow not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transport_manager():
    """Test the internal transport manager functionality."""
    from pipecat.transports import InternalTransportManager, TransportParams

    manager = InternalTransportManager()

    # Create transport pair
    params = TransportParams(
        audio_out_enabled=True,
        audio_in_enabled=True,
        audio_out_sample_rate=16000,
        audio_in_sample_rate=16000,
    )

    actor_transport, adversary_transport = manager.create_transport_pair(
        test_session_id="test-123", actor_params=params, adversary_params=params
    )

    # Verify transports are connected
    assert actor_transport._output._partner == adversary_transport._input
    assert adversary_transport._output._partner == actor_transport._input

    # Verify transport pair is tracked
    assert manager.get_active_test_count() == 1
    assert manager.get_transport_pair("test-123") is not None

    # Remove transport pair
    manager.remove_transport_pair("test-123")
    assert manager.get_active_test_count() == 0
    assert manager.get_transport_pair("test-123") is None
