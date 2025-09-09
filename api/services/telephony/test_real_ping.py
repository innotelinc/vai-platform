#!/usr/bin/env python3
"""Test script to verify real WebSocket ping frames are being sent."""

import asyncio
import os
import sys
from pathlib import Path

# Add the asyncari src to Python path
asyncari_path = Path(__file__).parent.parent.parent.parent.parent / "asyncari" / "src"
sys.path.insert(0, str(asyncari_path))

import asyncari
from loguru import logger

# Enable debug logging to see ping frames
logger.add(sys.stderr, level="DEBUG")


async def test_real_ping():
    """Test that real WebSocket ping frames are sent."""

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

            # Get the WebSocket
            for ws in client.websockets:
                logger.info(f"WebSocket type: {type(ws)}")
                logger.info(
                    f"WebSocket wrapper active: {'WebSocketWrapper' in str(type(ws))}"
                )

                # Check internal structure
                if hasattr(ws, "_websocket"):
                    inner_ws = ws._websocket
                    logger.info(f"Inner WebSocket type: {type(inner_ws)}")
                    logger.info(f"Has _connection: {hasattr(inner_ws, '_connection')}")
                    logger.info(f"Has _sock: {hasattr(inner_ws, '_sock')}")

                # Send a test ping
                logger.info("Sending test ping...")
                try:
                    await ws.ping(b"test-ping-123")
                    logger.info("Ping sent successfully!")
                except Exception as e:
                    logger.error(f"Ping failed: {e}")

            # Test the keep_alive function
            logger.info("\nTesting keep_alive function...")
            from ari_client_manager import keep_alive

            # Run keep_alive for a short time
            keep_alive_task = asyncio.create_task(keep_alive(client, interval=3.0))

            # Let it run for 10 seconds to see multiple pings
            await asyncio.sleep(10)

            # Cancel and cleanup
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

            logger.info("Test completed!")

    except Exception as e:
        logger.exception(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_real_ping())
