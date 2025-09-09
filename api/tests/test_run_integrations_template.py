from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.run_integrations import _process_slack_integration


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock the logger for all tests."""
    with patch("api.tasks.run_integrations.logger") as mock_logger:
        # Mock the bind method to return the logger itself
        mock_logger.bind.return_value = mock_logger
        yield mock_logger


@pytest.mark.asyncio
async def test_slack_integration_with_template():
    """Test that Slack integration uses render_template correctly."""
    # Mock integration
    mock_integration = MagicMock()
    mock_integration.id = 1
    mock_integration.organisation_id = 123
    mock_integration.connection_details = {
        "connection_config": {"incoming_webhook.url": "https://hooks.slack.com/test"}
    }

    # Mock gathered context
    gathered_context = {
        "call_disposition": "XFER",
        "mapped_call_disposition": "XFER",  # Required for Slack integration to proceed
        "call_duration": "300",
        "agent_name": "Alex",
    }

    # Mock db_client
    with patch("api.tasks.run_integrations.db_client") as mock_db_client:
        # Mock message template configuration
        mock_db_client.get_configuration_value = AsyncMock(
            return_value={
                "slack": {
                    "DISPOSITION_CODE": "Agent: {{agent_name}}\\nDisposition: {{call_disposition}}\\nDuration: {{call_duration}}s"
                }
            }
        )

        # Mock aiohttp session
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
            await _process_slack_integration(mock_integration, gathered_context)

            # Verify the message was formatted correctly
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args

            # Check the webhook URL
            assert call_args[0][0] == "https://hooks.slack.com/test"

            # Check the message content
            json_data = call_args[1]["json"]

            # Check that the template was rendered correctly
            expected_text = "Agent: Alex\nDisposition: XFER\nDuration: 300s"
            assert json_data["text"] == expected_text


@pytest.mark.asyncio
async def test_slack_integration_with_missing_template_vars():
    """Test template rendering with missing variables."""
    # Mock integration
    mock_integration = MagicMock()
    mock_integration.id = 1
    mock_integration.organisation_id = 123
    mock_integration.connection_details = {
        "connection_config": {"incoming_webhook.url": "https://hooks.slack.com/test"}
    }

    # Mock gathered context with missing values
    gathered_context = {
        "call_disposition": "XFER",
        "mapped_call_disposition": "XFER",  # Required for Slack integration to proceed
        # call_duration is missing
    }

    # Mock db_client
    with patch("api.tasks.run_integrations.db_client") as mock_db_client:
        # Mock message template configuration with fallback
        mock_db_client.get_configuration_value = AsyncMock(
            return_value={
                "slack": {
                    "DISPOSITION_CODE": "Disposition: {{call_disposition}}\\nDuration: {{call_duration | fallback:N/A}}"
                }
            }
        )

        # Mock aiohttp session
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
            await _process_slack_integration(mock_integration, gathered_context)

            # Check that the template was rendered with fallback
            json_data = mock_session.post.call_args[1]["json"]
            expected_text = "Disposition: XFER\nDuration: N/A"
            assert json_data["text"] == expected_text
