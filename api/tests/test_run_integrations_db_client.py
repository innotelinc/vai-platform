"""Tests for run_integrations with new DB client methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.enums import WorkflowRunMode
from api.tasks.run_integrations import run_integrations_post_workflow_run


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock the logger for all tests."""
    with patch("api.tasks.run_integrations.logger") as mock_logger:
        mock_logger.bind.return_value = mock_logger
        yield mock_logger


@pytest.fixture
def mock_workflow_run():
    """Create a mock workflow run with all required attributes."""
    workflow_run = MagicMock()
    workflow_run.id = 1
    workflow_run.mode = "browser"
    workflow_run.gathered_context = {
        "call_disposition": "XFER",
        "mapped_call_disposition": "XFER",  # Required for Slack integration
        "call_duration": "120",
        "agent_name": "TestAgent",
    }
    workflow_run.initial_context = {"vendor_id": "123"}

    # Setup workflow and user chain
    workflow_run.workflow = MagicMock()
    workflow_run.workflow.user = MagicMock()
    workflow_run.workflow.user.selected_organization_id = 100

    return workflow_run


@pytest.fixture
def mock_integration():
    """Create a mock integration."""
    integration = MagicMock()
    integration.id = 1
    integration.organisation_id = 100
    integration.provider = "slack"
    integration.is_active = True
    integration.connection_details = {
        "connection_config": {"incoming_webhook.url": "https://hooks.slack.com/test"}
    }
    return integration


@pytest.mark.asyncio
async def test_run_integrations_with_db_client_methods(
    mock_workflow_run, mock_integration
):
    """Test that run_integrations uses the new DB client methods correctly."""

    with patch("api.tasks.run_integrations.set_current_run_id") as mock_set_run_id:
        with patch("api.tasks.run_integrations.db_client") as mock_db_client:
            # Mock the new DB client methods
            mock_db_client.get_workflow_run_with_context = AsyncMock(
                return_value=(mock_workflow_run, 100)
            )
            mock_db_client.get_active_integrations_by_organization = AsyncMock(
                return_value=[mock_integration]
            )
            mock_db_client.get_configuration_value = AsyncMock(
                return_value={
                    "slack": {
                        "DISPOSITION_CODE": "Disposition: {{mapped_call_disposition}}"
                    }
                }
            )

            # Mock the aiohttp session for Slack webhook
            with patch(
                "api.tasks.run_integrations.aiohttp.ClientSession"
            ) as mock_session_class:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = AsyncMock()

                mock_post = MagicMock()
                mock_post.__aenter__.return_value = mock_response
                mock_post.__aexit__.return_value = AsyncMock()

                mock_session.post.return_value = mock_post
                mock_session_class.return_value = mock_session

                # Call the function
                await run_integrations_post_workflow_run(None, 1)

                # Verify the correct DB client methods were called
                mock_set_run_id.assert_called_once_with(1)
                mock_db_client.get_workflow_run_with_context.assert_called_once_with(1)
                mock_db_client.get_active_integrations_by_organization.assert_called_once_with(
                    100
                )

                # Verify the Slack webhook was called
                mock_session.post.assert_called_once()
                assert (
                    mock_session.post.call_args[0][0] == "https://hooks.slack.com/test"
                )


@pytest.mark.asyncio
async def test_run_integrations_no_workflow_run():
    """Test handling when workflow run is not found."""

    with patch("api.tasks.run_integrations.set_current_run_id"):
        with patch("api.tasks.run_integrations.db_client") as mock_db_client:
            # Mock workflow run not found
            mock_db_client.get_workflow_run_with_context = AsyncMock(
                return_value=(None, None)
            )

            # Call the function
            await run_integrations_post_workflow_run(None, 999)

            # Verify it returns early and doesn't call other DB methods
            mock_db_client.get_workflow_run_with_context.assert_called_once_with(999)
            mock_db_client.get_active_integrations_by_organization.assert_not_called()


@pytest.mark.asyncio
async def test_run_integrations_no_organization():
    """Test handling when user has no organization."""

    mock_workflow_run = MagicMock()
    mock_workflow_run.id = 1
    mock_workflow_run.gathered_context = {"test": "data"}
    mock_workflow_run.workflow = MagicMock()
    mock_workflow_run.workflow.user = MagicMock()

    with patch("api.tasks.run_integrations.set_current_run_id"):
        with patch("api.tasks.run_integrations.db_client") as mock_db_client:
            # Mock workflow run found but no organization
            mock_db_client.get_workflow_run_with_context = AsyncMock(
                return_value=(mock_workflow_run, None)
            )

            # Call the function
            await run_integrations_post_workflow_run(None, 1)

            # Verify it returns early after checking organization
            mock_db_client.get_workflow_run_with_context.assert_called_once_with(1)
            mock_db_client.get_active_integrations_by_organization.assert_not_called()


@pytest.mark.asyncio
async def test_run_integrations_no_gathered_context(mock_workflow_run):
    """Test handling when workflow run has no gathered context."""

    mock_workflow_run.gathered_context = None

    with patch("api.tasks.run_integrations.set_current_run_id"):
        with patch("api.tasks.run_integrations.db_client") as mock_db_client:
            # Mock workflow run with no gathered context
            mock_db_client.get_workflow_run_with_context = AsyncMock(
                return_value=(mock_workflow_run, 100)
            )

            # Call the function
            await run_integrations_post_workflow_run(None, 1)

            # Verify it returns early after checking gathered_context
            mock_db_client.get_workflow_run_with_context.assert_called_once_with(1)
            mock_db_client.get_active_integrations_by_organization.assert_not_called()


@pytest.mark.asyncio
async def test_run_integrations_stasis_mode(mock_workflow_run):
    """Test that stasis mode triggers vendor sync."""

    mock_workflow_run.mode = WorkflowRunMode.STASIS.value
    mock_workflow_run.initial_context = {
        "vendor": "test_vendor",
        "vendor_base_url": "https://api.vendor.com",
        "vendor_id": "123",
    }

    with patch("api.tasks.run_integrations.set_current_run_id"):
        with patch("api.tasks.run_integrations.db_client") as mock_db_client:
            with patch("api.tasks.run_integrations._sync_vendor_data") as mock_sync:
                mock_sync.return_value = None

                mock_db_client.get_workflow_run_with_context = AsyncMock(
                    return_value=(mock_workflow_run, 100)
                )
                mock_db_client.get_active_integrations_by_organization = AsyncMock(
                    return_value=[]
                )

                # Call the function
                await run_integrations_post_workflow_run(None, 1)

                # Verify vendor sync was called
                mock_sync.assert_called_once_with(
                    mock_workflow_run.initial_context,
                    mock_workflow_run.gathered_context,
                )


@pytest.mark.asyncio
async def test_run_integrations_multiple_integrations(mock_workflow_run):
    """Test processing multiple integrations."""

    # Create multiple mock integrations
    slack_integration = MagicMock()
    slack_integration.provider = "slack"
    slack_integration.connection_details = {
        "connection_config": {"incoming_webhook.url": "https://hooks.slack.com/test1"}
    }

    slack_integration2 = MagicMock()
    slack_integration2.provider = "slack"
    slack_integration2.connection_details = {
        "connection_config": {"incoming_webhook.url": "https://hooks.slack.com/test2"}
    }

    with patch("api.tasks.run_integrations.set_current_run_id"):
        with patch("api.tasks.run_integrations.db_client") as mock_db_client:
            mock_db_client.get_workflow_run_with_context = AsyncMock(
                return_value=(mock_workflow_run, 100)
            )
            mock_db_client.get_active_integrations_by_organization = AsyncMock(
                return_value=[slack_integration, slack_integration2]
            )
            mock_db_client.get_configuration_value = AsyncMock(
                return_value={"slack": {"DISPOSITION_CODE": "Test message"}}
            )

            with patch(
                "api.tasks.run_integrations.aiohttp.ClientSession"
            ) as mock_session_class:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = AsyncMock()

                mock_post = MagicMock()
                mock_post.__aenter__.return_value = mock_response
                mock_post.__aexit__.return_value = AsyncMock()

                mock_session.post.return_value = mock_post
                mock_session_class.return_value = mock_session

                # Call the function
                await run_integrations_post_workflow_run(None, 1)

                # Verify both integrations were processed
                assert mock_session.post.call_count == 2

                # Check that both webhooks were called
                call_urls = [call[0][0] for call in mock_session.post.call_args_list]
                assert "https://hooks.slack.com/test1" in call_urls
                assert "https://hooks.slack.com/test2" in call_urls
