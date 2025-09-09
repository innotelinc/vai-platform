from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.utils.enums import EndTaskReason

from api.services.pipecat.event_handlers import register_transport_event_handlers


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for event handlers."""
    # Store registered handlers
    registered_handlers = {}

    def mock_event_handler(event_name):
        def decorator(func):
            registered_handlers[event_name] = func
            return func

        return decorator

    mock_transport = MagicMock()
    mock_transport.event_handler = mock_event_handler

    mock_task = MagicMock()
    mock_task.cancel = AsyncMock()

    mock_engine = MagicMock()
    mock_engine.initialize = AsyncMock()
    mock_engine.cleanup = AsyncMock()

    mock_audio_buffer = MagicMock()
    mock_audio_buffer.start_recording = AsyncMock()
    mock_audio_buffer.stop_recording = AsyncMock()

    mock_usage_metrics_aggregator = MagicMock()
    mock_usage_metrics_aggregator.get_all_usage_metrics_serialized = MagicMock(
        return_value={"test": "metrics"}
    )

    return {
        "transport": mock_transport,
        "workflow_run_id": 123,
        "audio_buffer": mock_audio_buffer,
        "task": mock_task,
        "engine": mock_engine,
        "usage_metrics_aggregator": mock_usage_metrics_aggregator,
        "audio_synchronizer": None,
        "registered_handlers": registered_handlers,
    }


@pytest.mark.asyncio
async def test_transport_disconnect_reason_mapping(mock_dependencies):
    """Test that transport_disconnect_reason is mapped when no engine disconnect reason exists."""
    # Register event handlers
    register_transport_event_handlers(
        transport=mock_dependencies["transport"],
        workflow_run_id=mock_dependencies["workflow_run_id"],
        audio_buffer=mock_dependencies["audio_buffer"],
        task=mock_dependencies["task"],
        engine=mock_dependencies["engine"],
        usage_metrics_aggregator=mock_dependencies["usage_metrics_aggregator"],
        audio_synchronizer=mock_dependencies["audio_synchronizer"],
    )

    # Get the on_client_disconnected handler
    handler = mock_dependencies["registered_handlers"]["on_client_disconnected"]

    # Mock engine with no call disposition
    mock_dependencies["engine"].get_call_disposition.return_value = None
    mock_dependencies["engine"].get_gathered_context.return_value = {
        "agent_name": "Alex"
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.pipecat.event_handlers.get_organization_id_from_workflow_run",
        new_callable=AsyncMock,
    ) as mock_get_org_id:
        with patch(
            "api.services.pipecat.event_handlers.apply_disposition_mapping",
            new_callable=AsyncMock,
        ) as mock_apply_mapping:
            with patch(
                "api.services.pipecat.event_handlers.db_client"
            ) as mock_db_client:
                with patch(
                    "api.services.pipecat.event_handlers.enqueue_job"
                ) as mock_enqueue:
                    # Mock organization ID
                    mock_get_org_id.return_value = 1

                    # Mock call duration for user_hangup logic
                    mock_dependencies[
                        "usage_metrics_aggregator"
                    ].get_call_duration.return_value = 15

                    # Mock disposition mapping
                    async def apply_mapping_side_effect(value, org_id):
                        return {
                            "NIBP": "NOT_INTERESTED_BUSINESS_PURPOSE",
                            "user_qualified": "QUALIFIED",
                        }.get(value, value)

                    mock_apply_mapping.side_effect = apply_mapping_side_effect

                    # Mock database operations
                    mock_workflow_run = MagicMock()
                    mock_workflow_run.id = 123
                    mock_workflow_run.workflow_id = 1
                    mock_workflow_run.organization_id = 1
                    mock_workflow_run.gathered_context = {}
                    mock_db_client.get_workflow_run_by_id = AsyncMock(
                        return_value=mock_workflow_run
                    )
                    mock_db_client.update_workflow_run = AsyncMock()

                    # Call handler with transport_disconnect_reason
                    await handler(
                        mock_dependencies["transport"],
                        participant=None,
                        transport_disconnect_reason="user_hangup",
                    )

                    # Verify disposition mapping was applied with NIBP (since duration > 10)
                    mock_apply_mapping.assert_called_once_with("NIBP", 1)

                    # Verify database was updated with mapped value
                    mock_db_client.update_workflow_run.assert_called_once()
                    call_args = mock_db_client.update_workflow_run.call_args
                    assert (
                        call_args[1]["gathered_context"]["mapped_call_disposition"]
                        == "NOT_INTERESTED_BUSINESS_PURPOSE"
                    )

                    # Verify task was cancelled (no engine disconnect reason)
                    mock_dependencies["task"].cancel.assert_called_once()


@pytest.mark.asyncio
async def test_transport_disconnect_reason_user_hangup_short_call(mock_dependencies):
    """Test that user_hangup with short call duration is mapped to HU."""
    # Register event handlers
    register_transport_event_handlers(
        transport=mock_dependencies["transport"],
        workflow_run_id=mock_dependencies["workflow_run_id"],
        audio_buffer=mock_dependencies["audio_buffer"],
        task=mock_dependencies["task"],
        engine=mock_dependencies["engine"],
        usage_metrics_aggregator=mock_dependencies["usage_metrics_aggregator"],
        audio_synchronizer=mock_dependencies["audio_synchronizer"],
    )

    # Get the on_client_disconnected handler
    handler = mock_dependencies["registered_handlers"]["on_client_disconnected"]

    # Mock engine with no call disposition
    mock_dependencies["engine"].get_call_disposition.return_value = None
    mock_dependencies["engine"].get_gathered_context.return_value = {
        "agent_name": "Alex"
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.pipecat.event_handlers.get_organization_id_from_workflow_run",
        new_callable=AsyncMock,
    ) as mock_get_org_id:
        with patch(
            "api.services.pipecat.event_handlers.apply_disposition_mapping",
            new_callable=AsyncMock,
        ) as mock_apply_mapping:
            with patch(
                "api.services.pipecat.event_handlers.db_client"
            ) as mock_db_client:
                with patch(
                    "api.services.pipecat.event_handlers.enqueue_job"
                ) as mock_enqueue:
                    # Mock organization ID
                    mock_get_org_id.return_value = 1

                    # Mock call duration for user_hangup logic (< 10 seconds)
                    mock_dependencies[
                        "usage_metrics_aggregator"
                    ].get_call_duration.return_value = 5

                    # Mock disposition mapping
                    mock_apply_mapping.return_value = "HANGUP"

                    # Mock database operations
                    mock_workflow_run = MagicMock()
                    mock_workflow_run.id = 123
                    mock_workflow_run.workflow_id = 1
                    mock_workflow_run.organization_id = 1
                    mock_workflow_run.gathered_context = {}
                    mock_db_client.get_workflow_run_by_id = AsyncMock(
                        return_value=mock_workflow_run
                    )
                    mock_db_client.update_workflow_run = AsyncMock()

                    # Call handler with transport_disconnect_reason
                    await handler(
                        mock_dependencies["transport"],
                        participant=None,
                        transport_disconnect_reason="user_hangup",
                    )

                    # Verify disposition mapping was applied with HU (since duration < 10)
                    mock_apply_mapping.assert_called_once_with("HU", 1)

                    # Verify database was updated with mapped value
                    mock_db_client.update_workflow_run.assert_called_once()
                    call_args = mock_db_client.update_workflow_run.call_args
                    assert (
                        call_args[1]["gathered_context"]["mapped_call_disposition"]
                        == "HANGUP"
                    )

                    # Verify task was cancelled (no engine disconnect reason)
                    mock_dependencies["task"].cancel.assert_called_once()


@pytest.mark.asyncio
async def test_engine_disconnect_reason_takes_precedence(mock_dependencies):
    """Test that engine disconnect reason takes precedence and is not mapped."""
    # Register event handlers
    register_transport_event_handlers(
        transport=mock_dependencies["transport"],
        workflow_run_id=mock_dependencies["workflow_run_id"],
        audio_buffer=mock_dependencies["audio_buffer"],
        task=mock_dependencies["task"],
        engine=mock_dependencies["engine"],
        usage_metrics_aggregator=mock_dependencies["usage_metrics_aggregator"],
        audio_synchronizer=mock_dependencies["audio_synchronizer"],
    )

    # Get the on_client_disconnected handler
    handler = mock_dependencies["registered_handlers"]["on_client_disconnected"]

    # Mock engine with call disposition
    mock_dependencies["engine"].get_call_disposition.return_value = "user_qualified"
    mock_dependencies["engine"].get_gathered_context.return_value = {
        "agent_name": "Alex"
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.pipecat.event_handlers.get_organization_id_from_workflow_run",
        new_callable=AsyncMock,
    ) as mock_get_org_id:
        with patch(
            "api.services.pipecat.event_handlers.apply_disposition_mapping",
            new_callable=AsyncMock,
        ) as mock_apply_mapping:
            with patch(
                "api.services.pipecat.event_handlers.db_client"
            ) as mock_db_client:
                with patch(
                    "api.services.pipecat.event_handlers.enqueue_job"
                ) as mock_enqueue:
                    # Mock organization ID
                    mock_get_org_id.return_value = 1

                    # Mock disposition mapping for engine's reason
                    mock_apply_mapping.return_value = "QUALIFIED"

                    # Mock database operations
                    mock_workflow_run = MagicMock()
                    mock_workflow_run.id = 123
                    mock_workflow_run.workflow_id = 1
                    mock_workflow_run.organization_id = 1
                    mock_workflow_run.gathered_context = {}
                    mock_db_client.get_workflow_run_by_id = AsyncMock(
                        return_value=mock_workflow_run
                    )
                    mock_db_client.update_workflow_run = AsyncMock()

                    # Call handler with transport_disconnect_reason
                    await handler(
                        mock_dependencies["transport"],
                        participant=None,
                        transport_disconnect_reason="user_hangup",
                    )

                    # Verify disposition mapping was called with engine's reason
                    mock_apply_mapping.assert_called_once_with("user_qualified", 1)

                    # Verify database was updated with mapped value
                    mock_db_client.update_workflow_run.assert_called_once()
                    call_args = mock_db_client.update_workflow_run.call_args
                    assert (
                        call_args[1]["gathered_context"]["mapped_call_disposition"]
                        == "QUALIFIED"
                    )

                    # Verify task was NOT cancelled (engine disconnect reason exists)
                    mock_dependencies["task"].cancel.assert_not_called()


@pytest.mark.asyncio
async def test_no_disconnect_reason_uses_unknown(mock_dependencies):
    """Test that when no disconnect reason is provided, UNKNOWN is used."""
    # Register event handlers
    register_transport_event_handlers(
        transport=mock_dependencies["transport"],
        workflow_run_id=mock_dependencies["workflow_run_id"],
        audio_buffer=mock_dependencies["audio_buffer"],
        task=mock_dependencies["task"],
        engine=mock_dependencies["engine"],
        usage_metrics_aggregator=mock_dependencies["usage_metrics_aggregator"],
        audio_synchronizer=mock_dependencies["audio_synchronizer"],
    )

    # Get the on_client_disconnected handler
    handler = mock_dependencies["registered_handlers"]["on_client_disconnected"]

    # Mock engine with no call disposition
    mock_dependencies["engine"].get_call_disposition.return_value = None
    mock_dependencies["engine"].get_gathered_context.return_value = {
        "agent_name": "Alex"
    }

    with patch(
        "api.services.pipecat.event_handlers.get_organization_id_from_workflow_run"
    ) as mock_get_org_id:
        with patch(
            "api.services.pipecat.event_handlers.apply_disposition_mapping"
        ) as mock_apply_mapping:
            with patch(
                "api.services.pipecat.event_handlers.db_client"
            ) as mock_db_client:
                with patch(
                    "api.services.pipecat.event_handlers.enqueue_job"
                ) as mock_enqueue:
                    # Mock organization ID
                    mock_get_org_id.return_value = 1

                    # Mock disposition mapping - should return UNKNOWN as-is
                    mock_apply_mapping.return_value = EndTaskReason.UNKNOWN.value

                    # Mock database operations
                    mock_workflow_run = MagicMock()
                    mock_workflow_run.id = 123
                    mock_workflow_run.workflow_id = 1
                    mock_workflow_run.organization_id = 1
                    mock_workflow_run.gathered_context = {}
                    mock_db_client.get_workflow_run_by_id = AsyncMock(
                        return_value=mock_workflow_run
                    )
                    mock_db_client.update_workflow_run = AsyncMock()

                    # Call handler without transport_disconnect_reason
                    await handler(
                        mock_dependencies["transport"],
                        participant=None,
                        transport_disconnect_reason=None,
                    )

                    # Verify disposition mapping was called with UNKNOWN
                    mock_apply_mapping.assert_called_once_with(
                        EndTaskReason.UNKNOWN.value, 1
                    )

                    # Verify database was updated with UNKNOWN
                    mock_db_client.update_workflow_run.assert_called_once()
                    call_args = mock_db_client.update_workflow_run.call_args
                    assert (
                        call_args[1]["gathered_context"]["mapped_call_disposition"]
                        == EndTaskReason.UNKNOWN.value
                    )
