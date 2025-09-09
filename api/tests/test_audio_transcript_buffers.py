import os
import wave

import pytest

from api.services.pipecat.audio_transcript_buffers import (
    InMemoryAudioBuffer,
    InMemoryTranscriptBuffer,
)


@pytest.mark.asyncio
async def test_audio_buffer_append_and_write():
    """Test that audio buffer can append data and write to temp file."""
    buffer = InMemoryAudioBuffer(workflow_run_id=123, sample_rate=16000, num_channels=1)

    # Create some test PCM data
    test_pcm = b"\x00\x01" * 1000  # 2000 bytes

    # Append data
    await buffer.append(test_pcm)
    await buffer.append(test_pcm)

    assert buffer.size == 4000
    assert not buffer.is_empty

    # Write to temp file
    temp_path = await buffer.write_to_temp_file()

    try:
        # Verify file exists and is valid WAV
        assert os.path.exists(temp_path)

        with wave.open(temp_path, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            # Each frame is 2 bytes (16-bit), so 4000 bytes = 2000 frames
            assert wf.getnframes() == 2000
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_audio_buffer_memory_limit():
    """Test that audio buffer enforces memory limit."""
    buffer = InMemoryAudioBuffer(workflow_run_id=123, sample_rate=16000)

    # Set a smaller limit for testing
    buffer._max_size = 1000

    # This should work
    await buffer.append(b"\x00" * 500)

    # This should fail
    with pytest.raises(MemoryError):
        await buffer.append(b"\x00" * 600)


@pytest.mark.asyncio
async def test_transcript_buffer_append_and_write():
    """Test that transcript buffer can append data and write to temp file."""
    buffer = InMemoryTranscriptBuffer(workflow_run_id=456)

    # Append some transcript lines
    await buffer.append("[00:00:01] user: Hello\n")
    await buffer.append("[00:00:02] assistant: Hi there!\n")
    await buffer.append("[00:00:03] user: How are you?\n")

    assert not buffer.is_empty

    # Write to temp file
    temp_path = await buffer.write_to_temp_file()

    try:
        # Verify file exists and has correct content
        assert os.path.exists(temp_path)

        with open(temp_path, "r") as f:
            content = f.read()
            assert "[00:00:01] user: Hello\n" in content
            assert "[00:00:02] assistant: Hi there!\n" in content
            assert "[00:00:03] user: How are you?\n" in content
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_empty_buffers():
    """Test that empty buffers are handled correctly."""
    audio_buffer = InMemoryAudioBuffer(workflow_run_id=789, sample_rate=16000)
    transcript_buffer = InMemoryTranscriptBuffer(workflow_run_id=789)

    assert audio_buffer.is_empty
    assert transcript_buffer.is_empty

    # Should still be able to write empty files
    audio_path = await audio_buffer.write_to_temp_file()
    transcript_path = await transcript_buffer.write_to_temp_file()

    try:
        assert os.path.exists(audio_path)
        assert os.path.exists(transcript_path)

        # Empty WAV file should still have valid header
        with wave.open(audio_path, "rb") as wf:
            assert wf.getnframes() == 0

        # Empty transcript file
        with open(transcript_path, "r") as f:
            assert f.read() == ""
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(transcript_path):
            os.remove(transcript_path)
