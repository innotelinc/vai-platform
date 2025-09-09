"""
Test cases for _leave_counter mechanism in transport clients.

This test suite verifies that the _leave_counter prevents premature disconnection
when both input and output transports are using the same client.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from pipecat.frames.frames import EndFrame, StartFrame
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketCallbacks,
    FastAPIWebsocketClient,
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.transports.network.small_webrtc import SmallWebRTCClient

from api.services.telephony.stasis_rtp_client import StasisRTPClient


class TestLeaveCounterFastAPIWebsocket:
    """Test the _leave_counter mechanism in FastAPIWebsocketClient."""

    @pytest.mark.asyncio
    async def test_leave_counter_prevents_early_disconnect(self):
        """Test that disconnect only happens when both transports have disconnected."""
        # Create mock websocket
        mock_websocket = Mock()
        mock_websocket.close = AsyncMock()
        # Set client_state directly to WebSocketState.CONNECTED value
        from starlette.websockets import WebSocketState

        mock_websocket.client_state = WebSocketState.CONNECTED

        # Create callbacks
        callbacks = FastAPIWebsocketCallbacks(
            on_client_connected=AsyncMock(),
            on_client_disconnected=AsyncMock(),
            on_session_timeout=AsyncMock(),
        )

        # Create client
        client = FastAPIWebsocketClient(
            mock_websocket, is_binary=False, callbacks=callbacks
        )

        # Create StartFrame
        start_frame = StartFrame()

        # Simulate both input and output transports calling setup
        await client.setup(start_frame)  # Input transport
        assert client._leave_counter == 1

        await client.setup(start_frame)  # Output transport
        assert client._leave_counter == 2

        # First disconnect - should not actually disconnect
        await client.disconnect()
        assert client._leave_counter == 1
        mock_websocket.close.assert_not_called()
        callbacks.on_client_disconnected.assert_not_called()

        # Second disconnect - should actually disconnect
        await client.disconnect()
        assert client._leave_counter == 0
        mock_websocket.close.assert_called_once()
        callbacks.on_client_disconnected.assert_called_once()


class TestLeaveCounterStasisRTP:
    """Test the _leave_counter mechanism in StasisRTPClient."""

    @pytest.mark.asyncio
    async def test_leave_counter_prevents_early_disconnect(self):
        """Test that disconnect only happens when both transports have disconnected."""
        # Create mock connection
        mock_connection = Mock()
        mock_connection.is_connected.return_value = True
        mock_connection.disconnect = AsyncMock()
        mock_connection.notify_sockets_closed = AsyncMock()

        # Mock event_handler as a callable that acts as a decorator
        def mock_event_handler(event_name):
            def decorator(func):
                return func

            return decorator

        mock_connection.event_handler = mock_event_handler

        # Create callbacks
        from api.services.telephony.stasis_rtp_transport import StasisRTPCallbacks

        callbacks = StasisRTPCallbacks(
            on_client_connected=AsyncMock(),
            on_client_disconnected=AsyncMock(),
            on_client_closed=AsyncMock(),
        )

        # Create client
        client = StasisRTPClient(mock_connection, callbacks)

        # Create StartFrame
        start_frame = StartFrame()

        # Simulate both input and output transports calling setup
        await client.setup(start_frame)  # Input transport
        assert client._leave_counter == 1

        await client.setup(start_frame)  # Output transport
        assert client._leave_counter == 2

        # First disconnect - should not actually disconnect
        await client.disconnect()
        assert client._leave_counter == 1
        mock_connection.disconnect.assert_not_called()

        # Second disconnect - should actually disconnect
        await client.disconnect()
        assert client._leave_counter == 0
        mock_connection.disconnect.assert_called_once()


class TestLeaveCounterSmallWebRTC:
    """Test the _leave_counter mechanism in SmallWebRTCClient."""

    @pytest.mark.asyncio
    async def test_leave_counter_prevents_early_disconnect(self):
        """Test that disconnect only happens when both transports have disconnected."""
        # Create mock connection
        mock_connection = Mock()
        mock_connection.is_connected.return_value = True
        mock_connection.disconnect = AsyncMock()
        mock_connection.notify_sockets_closed = AsyncMock()

        # Mock event_handler as a callable that acts as a decorator
        def mock_event_handler(event_name):
            def decorator(func):
                return func

            return decorator

        mock_connection.event_handler = mock_event_handler

        # Create callbacks
        from pipecat.transports.network.small_webrtc import SmallWebRTCCallbacks

        callbacks = SmallWebRTCCallbacks(
            on_app_message=AsyncMock(),
            on_client_connected=AsyncMock(),
            on_client_disconnected=AsyncMock(),
        )

        # Create client
        client = SmallWebRTCClient(mock_connection, callbacks)

        # Create StartFrame with required attributes
        start_frame = StartFrame()

        # Create mock transport params
        from pipecat.transports.base_transport import TransportParams

        params = TransportParams(
            audio_in_channels=1, audio_in_sample_rate=16000, audio_out_sample_rate=16000
        )

        # Simulate both input and output transports calling setup
        await client.setup(params, start_frame)  # Input transport
        assert client._leave_counter == 1

        await client.setup(params, start_frame)  # Output transport
        assert client._leave_counter == 2

        # First disconnect - should not actually disconnect
        await client.disconnect()
        assert client._leave_counter == 1
        mock_connection.disconnect.assert_not_called()

        # Second disconnect - should actually disconnect
        await client.disconnect()
        assert client._leave_counter == 0
        mock_connection.disconnect.assert_called_once()


@pytest.mark.skip(reason="Complex integration test - requires additional mocking")
@pytest.mark.asyncio
async def test_transport_lifecycle_with_leave_counter():
    """Test complete transport lifecycle with proper leave counter handling."""
    # Create mock websocket
    mock_websocket = Mock()
    mock_websocket.close = AsyncMock()
    # Set client_state directly to WebSocketState.CONNECTED value
    from starlette.websockets import WebSocketState

    mock_websocket.client_state = WebSocketState.CONNECTED
    mock_websocket.iter_bytes = Mock(return_value=iter([]))
    mock_websocket.send_bytes = AsyncMock()

    # Create transport
    params = FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True)
    transport = FastAPIWebsocketTransport(mock_websocket, params)

    # Get input and output transports
    input_transport = transport.input()
    output_transport = transport.output()

    # Setup the transport with required components
    from pipecat.clocks.system_clock import SystemClock
    from pipecat.processors.frame_processor import FrameProcessorSetup
    from pipecat.utils.asyncio.task_manager import TaskManager, TaskManagerParams

    clock = SystemClock()
    task_manager = TaskManager()

    # Setup task manager with event loop
    loop = asyncio.get_event_loop()
    task_manager_params = TaskManagerParams(loop=loop)
    task_manager.setup(task_manager_params)

    setup = FrameProcessorSetup(clock=clock, task_manager=task_manager)

    # Setup both input and output transports
    await input_transport.setup(setup)
    await output_transport.setup(setup)

    # Start both transports
    start_frame = StartFrame()
    await input_transport.start(start_frame)
    await output_transport.start(start_frame)

    # Verify leave counter is 2
    assert transport._client._leave_counter == 2

    # Stop input transport
    end_frame = EndFrame()
    await input_transport.stop(end_frame)

    # Verify websocket not closed yet
    mock_websocket.close.assert_not_called()

    # Stop output transport
    await output_transport.stop(end_frame)

    # Now websocket should be closed
    mock_websocket.close.assert_called_once()
