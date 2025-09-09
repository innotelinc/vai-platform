#!/usr/bin/env python3
"""Test script to verify asyncari ping functionality."""

import asyncio
import os
import sys
from pathlib import Path

# Add the asyncari src to Python path for testing
asyncari_path = Path(__file__).parent.parent.parent.parent.parent / "asyncari" / "src"
sys.path.insert(0, str(asyncari_path))

import asyncari
from loguru import logger


async def test_ping():
    """Test the ping functionality with asyncari."""

    # Configure from environment or use defaults
    base_url = os.getenv("ARI_STASIS_ENDPOINT", "http://localhost:8088")
    username = os.getenv("ARI_STASIS_USER", "asterisk")
    password = os.getenv("ARI_STASIS_USER_PASSWORD", "asterisk")
    apps = os.getenv("ARI_STASIS_APP_NAME", "test-app")

    logger.info(f"Connecting to ARI at {base_url}")

    try:
        async with asyncari.connect(
            base_url=base_url, apps=apps, username=username, password=password
        ) as client:
            logger.info("Connected to ARI")

            # Test REST API ping
            logger.info("Testing REST API ping...")
            result = await client.asterisk.ping()
            logger.info(f"REST API ping successful: {result}")

            # Test WebSocket ping (should work with our wrapper)
            logger.info("Testing WebSocket ping...")
            for ws in client.websockets:
                try:
                    await ws.ping()
                    logger.info("WebSocket ping() called successfully (no-op)")
                except AttributeError:
                    logger.error("WebSocket doesn't have ping() method")
                except Exception as e:
                    logger.error(f"WebSocket ping failed: {e}")

            # Test the keep_alive function
            from ari_client_manager import keep_alive

            logger.info("Starting keep_alive task...")
            keep_alive_task = asyncio.create_task(keep_alive(client, interval=5.0))

            # Run for 20 seconds to see several pings
            await asyncio.sleep(20)

            # Cancel keep_alive
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                logger.info("keep_alive task cancelled")

            logger.info("Test completed successfully!")

    except Exception as e:
        logger.exception(f"Test failed: {e}")
        return False

    return True


async def test_with_manager():
    """Test using the ARI client manager."""
    from ari_client_manager import setup_ari_client_supervisor

    async def on_stasis_call(client, channel, context_vars):
        logger.info(f"Received call: {channel.id}")

    # Enable ARI Stasis for testing
    os.environ["ENABLE_ARI_STASIS"] = "true"

    supervisor = await setup_ari_client_supervisor(on_stasis_call)

    if supervisor:
        logger.info("ARI Stasis supervisor started with ping support")

        # Run for 30 seconds
        await asyncio.sleep(30)

        await supervisor.close()
        logger.info("Supervisor closed")
    else:
        logger.error("Failed to start supervisor")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "manager":
        asyncio.run(test_with_manager())
    else:
        asyncio.run(test_ping())
