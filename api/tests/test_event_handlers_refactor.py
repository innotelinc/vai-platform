from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.event_handlers import (
    register_audio_data_handler,
    register_transcript_handler,
    register_transport_event_handlers,
)


@pytest.mark.asyncio
async def test_transport_handlers_with_in_memory_buffers():
    """Test that transport handlers create and return in-memory buffers."""
    # Mock dependencies
    transport = MagicMock()
    transport.event_handler = lambda event_name: lambda func: func

    audio_buffer = AsyncMock()
    audio_synchronizer = AsyncMock()
    task = AsyncMock()
    engine = AsyncMock()
    engine.get_call_disposition.return_value = None
    engine.get_gathered_context.return_value = {}

    usage_metrics_aggregator = AsyncMock()
    usage_metrics_aggregator.get_call_duration.return_value = 30
    usage_metrics_aggregator.get_all_usage_metrics_serialized.return_value = {}

    # Create test audio config
    audio_config = AudioConfig(
        transport_in_sample_rate=16000,
        transport_out_sample_rate=16000,
        pipeline_sample_rate=16000,
    )

    # Register handlers
    audio_buf, transcript_buf = register_transport_event_handlers(
        transport=transport,
        workflow_run_id=123,
        audio_buffer=audio_buffer,
        task=task,
        engine=engine,
        usage_metrics_aggregator=usage_metrics_aggregator,
        audio_synchronizer=audio_synchronizer,
        audio_config=audio_config,
    )

    # Verify buffers were created with correct configuration
    assert audio_buf is not None
    assert transcript_buf is not None
    assert audio_buf._workflow_run_id == 123
    assert audio_buf._sample_rate == 16000
    assert audio_buf._num_channels == 1
    assert transcript_buf._workflow_run_id == 123


@pytest.mark.asyncio
async def test_audio_handler_with_in_memory_buffer():
    """Test audio handler uses in-memory buffer when provided."""
    # Mock audio synchronizer
    audio_synchronizer = MagicMock()
    handlers = {}

    def mock_event_handler(event_name):
        def decorator(func):
            handlers[event_name] = func
            return func

        return decorator

    audio_synchronizer.event_handler = mock_event_handler

    # Mock in-memory buffer
    in_memory_buffer = AsyncMock()

    # Register handler with buffer
    register_audio_data_handler(
        audio_synchronizer, workflow_run_id=123, in_memory_buffer=in_memory_buffer
    )

    # Test the handler
    assert "on_merged_audio" in handlers
    handler = handlers["on_merged_audio"]

    # Call handler with test data
    test_pcm = b"test_audio_data"
    await handler(None, test_pcm, 16000, 1)

    # Verify buffer was used
    in_memory_buffer.append.assert_called_once_with(test_pcm)


@pytest.mark.asyncio
async def test_transcript_handler_with_in_memory_buffer():
    """Test transcript handler uses in-memory buffer when provided."""
    # Mock transcript processor
    transcript = MagicMock()
    handlers = {}

    def mock_event_handler(event_name):
        def decorator(func):
            handlers[event_name] = func
            return func

        return decorator

    transcript.event_handler = mock_event_handler

    # Mock in-memory buffer
    in_memory_buffer = AsyncMock()

    # Register handler with buffer
    register_transcript_handler(
        transcript, workflow_run_id=456, in_memory_buffer=in_memory_buffer
    )

    # Create test frame
    test_frame = MagicMock()
    test_frame.messages = [
        MagicMock(timestamp="00:00:01", role="user", content="Hello"),
        MagicMock(timestamp="00:00:02", role="assistant", content="Hi there"),
    ]

    # Test the handler
    handler = handlers["on_transcript_update"]
    await handler(None, test_frame)

    # Verify buffer was used with correct format
    expected_text = "[00:00:01] user: Hello\n[00:00:02] assistant: Hi there\n"
    in_memory_buffer.append.assert_called_once_with(expected_text)


@pytest.mark.asyncio
async def test_audio_config_sample_rates():
    """Test that different audio configs result in correct sample rates."""
    # Mock dependencies
    transport = MagicMock()
    transport.event_handler = lambda event_name: lambda func: func

    audio_buffer = AsyncMock()
    audio_synchronizer = AsyncMock()
    task = AsyncMock()
    engine = AsyncMock()
    engine.get_call_disposition.return_value = None
    engine.get_gathered_context.return_value = {}

    usage_metrics_aggregator = AsyncMock()
    usage_metrics_aggregator.get_all_usage_metrics_serialized.return_value = {}

    # Test with 8kHz audio config (e.g., for Stasis/Twilio)
    audio_config_8k = AudioConfig(
        transport_in_sample_rate=8000,
        transport_out_sample_rate=8000,
        pipeline_sample_rate=8000,
    )

    audio_buf_8k, _ = register_transport_event_handlers(
        transport=transport,
        workflow_run_id=456,
        audio_buffer=audio_buffer,
        task=task,
        engine=engine,
        usage_metrics_aggregator=usage_metrics_aggregator,
        audio_synchronizer=audio_synchronizer,
        audio_config=audio_config_8k,
    )

    assert audio_buf_8k._sample_rate == 8000

    # Test with no audio config (should default to 16kHz)
    audio_buf_default, _ = register_transport_event_handlers(
        transport=transport,
        workflow_run_id=789,
        audio_buffer=audio_buffer,
        task=task,
        engine=engine,
        usage_metrics_aggregator=usage_metrics_aggregator,
        audio_synchronizer=audio_synchronizer,
        audio_config=None,
    )

    assert audio_buf_default._sample_rate == 16000
