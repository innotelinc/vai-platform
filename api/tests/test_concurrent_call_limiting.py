"""Tests for concurrent call limiting functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.enums import OrganizationConfigurationKey
from api.services.campaign.rate_limiter import RateLimiter


class TestConcurrentCallLimiting:
    """Test suite for concurrent call limiting."""

    @pytest.mark.asyncio
    async def test_acquire_concurrent_slot_success(self):
        """Test successful acquisition of concurrent slot."""
        rate_limiter = RateLimiter()

        # Mock Redis client
        with patch.object(rate_limiter, "_get_redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.eval = AsyncMock(return_value="test_slot_123")
            mock_redis.return_value = mock_client

            # Try to acquire slot
            slot_id = await rate_limiter.try_acquire_concurrent_slot(
                organization_id=1, max_concurrent=20
            )

            assert slot_id == "test_slot_123"
            mock_client.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_concurrent_slot_limit_reached(self):
        """Test slot acquisition when limit is reached."""
        rate_limiter = RateLimiter()

        # Mock Redis client
        with patch.object(rate_limiter, "_get_redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.eval = AsyncMock(return_value=None)  # Limit reached
            mock_redis.return_value = mock_client

            # Try to acquire slot
            slot_id = await rate_limiter.try_acquire_concurrent_slot(
                organization_id=1, max_concurrent=20
            )

            assert slot_id is None
            mock_client.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_concurrent_slot(self):
        """Test releasing a concurrent slot."""
        rate_limiter = RateLimiter()

        # Mock Redis client
        with patch.object(rate_limiter, "_get_redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.zrem = AsyncMock(return_value=1)  # Successfully removed
            mock_redis.return_value = mock_client

            # Release slot
            success = await rate_limiter.release_concurrent_slot(
                organization_id=1, slot_id="test_slot_123"
            )

            assert success is True
            mock_client.zrem.assert_called_once_with(
                "concurrent_calls:1", "test_slot_123"
            )

    @pytest.mark.asyncio
    async def test_get_concurrent_count(self):
        """Test getting current concurrent call count."""
        rate_limiter = RateLimiter()

        # Mock Redis client
        with patch.object(rate_limiter, "_get_redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.zremrangebyscore = AsyncMock()  # Cleanup stale entries
            mock_client.zcard = AsyncMock(return_value=5)  # 5 active calls
            mock_redis.return_value = mock_client

            # Get count
            count = await rate_limiter.get_concurrent_count(organization_id=1)

            assert count == 5
            mock_client.zremrangebyscore.assert_called_once()
            mock_client.zcard.assert_called_once()

    @pytest.mark.asyncio
    async def test_stale_entry_cleanup(self):
        """Test that stale entries are cleaned up automatically."""
        rate_limiter = RateLimiter()

        # Mock Redis client
        with patch.object(rate_limiter, "_get_redis") as mock_redis:
            mock_client = AsyncMock()

            # Mock eval to simulate cleanup in Lua script
            mock_client.eval = AsyncMock(return_value="new_slot_123")
            mock_redis.return_value = mock_client

            # Try to acquire slot (which should trigger cleanup)
            slot_id = await rate_limiter.try_acquire_concurrent_slot(
                organization_id=1, max_concurrent=20
            )

            assert slot_id == "new_slot_123"

            # Verify Lua script was called with proper stale cutoff
            call_args = mock_client.eval.call_args[0]
            lua_script = call_args[0]
            assert "ZREMRANGEBYSCORE" in lua_script  # Cleanup command in script

    @pytest.mark.asyncio
    async def test_workflow_slot_mapping_operations(self):
        """Test storing, retrieving, and deleting workflow slot mappings."""
        rate_limiter = RateLimiter()

        # Mock Redis client
        with patch.object(rate_limiter, "_get_redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.hset = AsyncMock(return_value=1)
            mock_client.expire = AsyncMock(return_value=True)
            mock_client.hgetall = AsyncMock(
                return_value={"org_id": "1", "slot_id": "test_slot_123"}
            )
            mock_client.delete = AsyncMock(return_value=1)
            mock_redis.return_value = mock_client

            # Test storing mapping
            success = await rate_limiter.store_workflow_slot_mapping(
                workflow_run_id=999, organization_id=1, slot_id="test_slot_123"
            )
            assert success is True
            mock_client.hset.assert_called_once()
            mock_client.expire.assert_called_once()

            # Test retrieving mapping
            mapping = await rate_limiter.get_workflow_slot_mapping(workflow_run_id=999)
            assert mapping == (1, "test_slot_123")
            mock_client.hgetall.assert_called_once_with("workflow_slot_mapping:999")

            # Test deleting mapping
            deleted = await rate_limiter.delete_workflow_slot_mapping(
                workflow_run_id=999
            )
            assert deleted is True
            mock_client.delete.assert_called_once_with("workflow_slot_mapping:999")


class TestCampaignCallDispatcher:
    """Test suite for CampaignCallDispatcher with concurrent limiting."""

    @pytest.mark.asyncio
    async def test_dispatch_call_waits_for_slot(self):
        """Test that dispatch_call waits for available slot."""
        from api.services.campaign.call_dispatcher import CampaignCallDispatcher

        dispatcher = CampaignCallDispatcher()

        # Mock dependencies
        mock_campaign = MagicMock(
            organization_id=1, workflow_id=123, id=456, created_by=789
        )
        mock_queued_run = MagicMock(
            id=111, context_variables={"phone_number": "+1234567890"}
        )

        # Mock rate limiter to simulate waiting
        slot_acquired = False
        call_count = 0

        async def mock_try_acquire(org_id, max_concurrent):
            nonlocal slot_acquired, call_count
            call_count += 1
            if call_count > 2:  # Succeed on third try
                slot_acquired = True
                return "test_slot_123"
            return None

        with patch(
            "api.services.campaign.call_dispatcher.rate_limiter"
        ) as mock_limiter:
            mock_limiter.try_acquire_concurrent_slot = AsyncMock(
                side_effect=mock_try_acquire
            )
            mock_limiter.release_concurrent_slot = AsyncMock()
            mock_limiter.store_workflow_slot_mapping = AsyncMock(return_value=True)

            with patch("api.services.campaign.call_dispatcher.db_client") as mock_db:
                mock_db.get_configuration = AsyncMock(return_value=None)
                mock_db.get_workflow_by_id = AsyncMock(
                    return_value=MagicMock(template_context_variables={})
                )
                mock_db.create_workflow_run = AsyncMock(
                    return_value=MagicMock(id=999, logs={})
                )

                with patch.object(
                    dispatcher.twilio_service, "initiate_call"
                ) as mock_twilio:
                    mock_twilio.return_value = {"sid": "test_sid"}

                    # Dispatch call (should wait and retry)
                    workflow_run = await dispatcher.dispatch_call(
                        mock_queued_run, mock_campaign
                    )

                    assert workflow_run is not None
                    assert slot_acquired is True
                    assert call_count == 3  # Tried 3 times
                    assert mock_limiter.try_acquire_concurrent_slot.call_count == 3

    @pytest.mark.asyncio
    async def test_dispatch_call_stores_slot_mapping(self):
        """Test that dispatch_call stores slot mapping in Redis."""
        from api.services.campaign.call_dispatcher import CampaignCallDispatcher

        dispatcher = CampaignCallDispatcher()

        # Mock dependencies
        mock_campaign = MagicMock(
            organization_id=1, workflow_id=123, id=456, created_by=789
        )
        mock_queued_run = MagicMock(
            id=111, context_variables={"phone_number": "+1234567890"}
        )

        with patch(
            "api.services.campaign.call_dispatcher.rate_limiter"
        ) as mock_limiter:
            mock_limiter.try_acquire_concurrent_slot = AsyncMock(
                return_value="test_slot_123"
            )
            mock_limiter.store_workflow_slot_mapping = AsyncMock(return_value=True)

            with patch("api.services.campaign.call_dispatcher.db_client") as mock_db:
                mock_db.get_configuration = AsyncMock(return_value=None)
                mock_db.get_workflow_by_id = AsyncMock(
                    return_value=MagicMock(template_context_variables={})
                )
                mock_db.create_workflow_run = AsyncMock(
                    return_value=MagicMock(id=999, logs={})
                )

                with patch.object(
                    dispatcher.twilio_service, "initiate_call"
                ) as mock_twilio:
                    mock_twilio.return_value = {"sid": "test_sid"}

                    # Dispatch call
                    workflow_run = await dispatcher.dispatch_call(
                        mock_queued_run, mock_campaign
                    )

                    # Verify slot mapping was stored
                    mock_limiter.store_workflow_slot_mapping.assert_called_once_with(
                        999, 1, "test_slot_123"
                    )

    @pytest.mark.asyncio
    async def test_org_specific_concurrent_limit(self):
        """Test that organization-specific concurrent limit is used."""
        from api.services.campaign.call_dispatcher import CampaignCallDispatcher

        dispatcher = CampaignCallDispatcher()

        # Mock db_client to return org-specific limit
        with patch("api.services.campaign.call_dispatcher.db_client") as mock_db:
            mock_config = MagicMock(value={"value": 10})  # Org limit is 10
            mock_db.get_configuration = AsyncMock(return_value=mock_config)

            # Get org limit
            limit = await dispatcher.get_org_concurrent_limit(organization_id=1)

            assert limit == 10  # Should use org-specific limit
            mock_db.get_configuration.assert_called_once_with(
                1, OrganizationConfigurationKey.CONCURRENT_CALL_LIMIT.value
            )

    @pytest.mark.asyncio
    async def test_default_concurrent_limit(self):
        """Test that default limit is used when org config not found."""
        from api.services.campaign.call_dispatcher import CampaignCallDispatcher

        dispatcher = CampaignCallDispatcher()

        # Mock db_client to return None (no config)
        with patch("api.services.campaign.call_dispatcher.db_client") as mock_db:
            mock_db.get_configuration = AsyncMock(return_value=None)

            # Get org limit
            limit = await dispatcher.get_org_concurrent_limit(organization_id=1)

            assert limit == 20  # Should use default limit

    @pytest.mark.asyncio
    async def test_release_call_slot(self):
        """Test releasing call slot when workflow completes."""
        from api.services.campaign.call_dispatcher import CampaignCallDispatcher

        dispatcher = CampaignCallDispatcher()

        # Mock rate limiter
        with patch(
            "api.services.campaign.call_dispatcher.rate_limiter"
        ) as mock_limiter:
            # Mock getting the slot mapping from Redis
            mock_limiter.get_workflow_slot_mapping = AsyncMock(
                return_value=(1, "test_slot_123")
            )
            mock_limiter.release_concurrent_slot = AsyncMock(return_value=True)
            mock_limiter.delete_workflow_slot_mapping = AsyncMock(return_value=True)

            # Release slot
            success = await dispatcher.release_call_slot(workflow_run_id=999)

            assert success is True
            mock_limiter.get_workflow_slot_mapping.assert_called_once_with(999)
            mock_limiter.release_concurrent_slot.assert_called_once_with(
                1, "test_slot_123"
            )
            mock_limiter.delete_workflow_slot_mapping.assert_called_once_with(999)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
