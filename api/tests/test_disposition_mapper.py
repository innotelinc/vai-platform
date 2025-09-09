from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.workflow.disposition_mapper import (
    apply_disposition_mapping,
    get_organization_id_from_workflow_run,
)


@pytest.mark.asyncio
async def test_apply_disposition_mapping_with_valid_mapping():
    """Test disposition mapping with valid configuration."""
    with patch("api.services.workflow.disposition_mapper.db_client") as mock_db_client:
        # Mock disposition mapping configuration
        mock_db_client.get_configuration_value = AsyncMock(
            return_value={
                "XFER": "TRANSFERRED",
                "ND": "NOT_QUALIFIED",
                "user_hangup": "HANGUP",
            }
        )

        # Test mapping exists
        result = await apply_disposition_mapping("XFER", 1)
        assert result == "TRANSFERRED"

        # Test mapping doesn't exist
        result = await apply_disposition_mapping("UNKNOWN", 1)
        assert result == "UNKNOWN"

        # Verify db_client was called correctly
        mock_db_client.get_configuration_value.assert_called_with(
            1, "DISPOSITION_CODE_MAPPING", default={}
        )


@pytest.mark.asyncio
async def test_apply_disposition_mapping_no_organization_id():
    """Test disposition mapping with no organization ID."""
    # Should return original value
    result = await apply_disposition_mapping("XFER", None)
    assert result == "XFER"


@pytest.mark.asyncio
async def test_apply_disposition_mapping_empty_value():
    """Test disposition mapping with empty value."""
    # Should return original empty value
    result = await apply_disposition_mapping("", 1)
    assert result == ""


@pytest.mark.asyncio
async def test_apply_disposition_mapping_error_handling():
    """Test disposition mapping handles errors gracefully."""
    with patch("api.services.workflow.disposition_mapper.db_client") as mock_db_client:
        # Mock database error
        mock_db_client.get_configuration_value = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Should return original value on error
        result = await apply_disposition_mapping("XFER", 1)
        assert result == "XFER"


@pytest.mark.asyncio
async def test_get_organization_id_from_workflow_run():
    """Test getting organization ID from workflow run ID."""
    with patch("api.services.workflow.disposition_mapper.db_client") as mock_db_client:
        # Mock workflow run with organization
        mock_workflow_run = MagicMock()
        mock_workflow_run.workflow.user.selected_organization_id = 123
        mock_db_client.get_workflow_run_by_id = AsyncMock(
            return_value=mock_workflow_run
        )

        result = await get_organization_id_from_workflow_run(1)
        assert result == 123

        # Verify db_client was called correctly
        mock_db_client.get_workflow_run_by_id.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_organization_id_no_workflow_run():
    """Test getting organization ID when workflow run doesn't exist."""
    with patch("api.services.workflow.disposition_mapper.db_client") as mock_db_client:
        # Mock no workflow run found
        mock_db_client.get_workflow_run_by_id = AsyncMock(return_value=None)

        result = await get_organization_id_from_workflow_run(1)
        assert result is None


@pytest.mark.asyncio
async def test_get_organization_id_no_user():
    """Test getting organization ID when workflow has no user."""
    with patch("api.services.workflow.disposition_mapper.db_client") as mock_db_client:
        # Mock workflow run with no user
        mock_workflow_run = MagicMock()
        mock_workflow_run.workflow.user = None
        mock_db_client.get_workflow_run_by_id = AsyncMock(
            return_value=mock_workflow_run
        )

        result = await get_organization_id_from_workflow_run(1)
        assert result is None


@pytest.mark.asyncio
async def test_get_organization_id_error_handling():
    """Test getting organization ID handles errors gracefully."""
    with patch("api.services.workflow.disposition_mapper.db_client") as mock_db_client:
        # Mock database error
        mock_db_client.get_workflow_run_by_id = AsyncMock(
            side_effect=Exception("Database error")
        )

        result = await get_organization_id_from_workflow_run(1)
        assert result is None
