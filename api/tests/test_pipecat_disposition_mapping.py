from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.workflow.pipecat_engine import PipecatEngine


def create_disposition_mapping_side_effect(mapping_dict):
    """Helper to create a side effect function for disposition mapping."""

    async def side_effect(value, org_id):
        return mapping_dict.get(value, value)

    return side_effect


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for PipecatEngine."""
    mock_task = MagicMock()
    mock_task.queue_frame = AsyncMock()

    mock_llm = MagicMock()
    mock_context = MagicMock()
    mock_workflow = MagicMock()

    return {
        "task": mock_task,
        "llm": mock_llm,
        "context": mock_context,
        "workflow": mock_workflow,
        "call_context_vars": {},
        "workflow_run_id": 123,
    }


@pytest.mark.asyncio
async def test_apply_disposition_mapping_with_call_disposition(mock_dependencies):
    """Test disposition mapping when call_disposition is present."""
    engine = PipecatEngine(**mock_dependencies)

    # Setup gathered context
    engine._gathered_context = {
        "call_disposition": "XFER",
        "agent_name": "Alex",
        "total_debt": "$15000",
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.workflow.pipecat_engine.get_organization_id_from_workflow_run"
    ) as mock_get_org_id:
        with patch(
            "api.services.workflow.pipecat_engine.apply_disposition_mapping"
        ) as mock_apply_mapping:
            # Mock organization ID
            mock_get_org_id.return_value = 1

            # Mock disposition mapping
            mock_apply_mapping.side_effect = create_disposition_mapping_side_effect(
                {
                    "XFER": "TRANSFERRED",
                    "ND": "NOT_QUALIFIED",
                }
            )

            # Call send_end_task_frame
            await engine.send_end_task_frame(reason="user_qualified")

            # Verify the frame was queued with mapped values
            mock_dependencies["task"].queue_frame.assert_called_once()
            frame = mock_dependencies["task"].queue_frame.call_args[0][0]

            # Check metadata contains mapped values
            assert frame.metadata["reason"] == "user_qualified"  # No mapping for this
            assert (
                frame.metadata["call_transfer_context"]["disposition"] == "TRANSFERRED"
            )

            # Check gathered context was updated
            assert engine._gathered_context["call_disposition"] == "TRANSFERRED"


@pytest.mark.asyncio
async def test_apply_disposition_mapping_with_disconnect_reason(mock_dependencies):
    """Test disposition mapping for disconnect_reason when no call_disposition exists."""
    engine = PipecatEngine(**mock_dependencies)

    # Setup gathered context without call_disposition
    engine._gathered_context = {
        "agent_name": "Alex",
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.workflow.pipecat_engine.get_organization_id_from_workflow_run"
    ) as mock_get_org_id:
        with patch(
            "api.services.workflow.pipecat_engine.apply_disposition_mapping"
        ) as mock_apply_mapping:
            # Mock organization ID
            mock_get_org_id.return_value = 1

            # Mock disposition mapping
            mock_apply_mapping.side_effect = create_disposition_mapping_side_effect(
                {
                    "user_qualified": "QUALIFIED",
                    "user_disqualified": "NOT_QUALIFIED",
                    "user_hangup": "HANGUP",
                }
            )

            # Call send_end_task_frame with a mappable reason
            await engine.send_end_task_frame(reason="user_qualified")

            # Verify the frame was queued with mapped disposition
            mock_dependencies["task"].queue_frame.assert_called_once()
            frame = mock_dependencies["task"].queue_frame.call_args[0][0]

            # Check metadata contains original reason
            assert frame.metadata["reason"] == "user_qualified"

            # Check call_transfer_context has mapped disconnect_reason as disposition
            assert frame.metadata["call_transfer_context"]["disposition"] == "QUALIFIED"

            # Check gathered context was updated with mapped call_disposition
            assert engine._gathered_context["call_disposition"] == "QUALIFIED"

            # Check internal call_disposition stores mapped value
            assert engine._call_disposition == "QUALIFIED"


@pytest.mark.asyncio
async def test_call_disposition_takes_precedence(mock_dependencies):
    """Test that call_disposition is used when both call_disposition and reason could be mapped."""
    engine = PipecatEngine(**mock_dependencies)

    # Setup gathered context with call_disposition
    engine._gathered_context = {
        "call_disposition": "XFER",
        "agent_name": "Alex",
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.workflow.pipecat_engine.get_organization_id_from_workflow_run"
    ) as mock_get_org_id:
        with patch(
            "api.services.workflow.pipecat_engine.apply_disposition_mapping"
        ) as mock_apply_mapping:
            # Mock organization ID
            mock_get_org_id.return_value = 1

            # Mock disposition mapping
            mock_apply_mapping.side_effect = create_disposition_mapping_side_effect(
                {
                    "XFER": "TRANSFERRED",
                    "user_qualified": "QUALIFIED",
                }
            )

            # Call send_end_task_frame with a reason that could also be mapped
            await engine.send_end_task_frame(reason="user_qualified")

            # Verify the frame was queued
            mock_dependencies["task"].queue_frame.assert_called_once()
            frame = mock_dependencies["task"].queue_frame.call_args[0][0]

            # Check that call_disposition mapping was used, not reason mapping
            assert (
                frame.metadata["call_transfer_context"]["disposition"] == "TRANSFERRED"
            )

            # Check only call_disposition was updated in gathered context
            assert engine._gathered_context["call_disposition"] == "TRANSFERRED"
            assert "disconnect_reason" not in engine._gathered_context


@pytest.mark.asyncio
async def test_disposition_mapping_no_organization_id(mock_dependencies):
    """Test when organization_id cannot be retrieved."""
    # Set workflow_run_id to None
    mock_dependencies["workflow_run_id"] = None
    engine = PipecatEngine(**mock_dependencies)

    engine._gathered_context = {
        "call_disposition": "XFER",
    }

    # Call send_end_task_frame
    await engine.send_end_task_frame(reason="user_qualified")

    # Verify the frame was queued with original values (no mapping)
    mock_dependencies["task"].queue_frame.assert_called_once()
    frame = mock_dependencies["task"].queue_frame.call_args[0][0]

    # Check values remain unchanged
    assert frame.metadata["reason"] == "user_qualified"
    assert frame.metadata["call_transfer_context"]["disposition"] == "XFER"

    # Gathered context should remain unchanged
    assert engine._gathered_context["call_disposition"] == "XFER"


@pytest.mark.asyncio
async def test_disposition_mapping_no_configuration(mock_dependencies):
    """Test when no disposition mapping is configured."""
    engine = PipecatEngine(**mock_dependencies)

    engine._gathered_context = {
        "call_disposition": "XFER",
    }

    # Mock the disposition mapper functions
    with patch(
        "api.services.workflow.pipecat_engine.get_organization_id_from_workflow_run"
    ) as mock_get_org_id:
        with patch(
            "api.services.workflow.pipecat_engine.apply_disposition_mapping"
        ) as mock_apply_mapping:
            # Mock organization ID
            mock_get_org_id.return_value = 1

            # Mock no disposition mapping (return original value)
            mock_apply_mapping.side_effect = lambda value, org_id: value

            # Call send_end_task_frame
            await engine.send_end_task_frame(reason="user_qualified")

            # Verify the frame was queued with original values
            mock_dependencies["task"].queue_frame.assert_called_once()
            frame = mock_dependencies["task"].queue_frame.call_args[0][0]

            # Check values remain unchanged
            assert frame.metadata["reason"] == "user_qualified"
            assert frame.metadata["call_transfer_context"]["disposition"] == "XFER"
