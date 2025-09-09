import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from api.tasks.s3_upload import upload_audio_to_s3, upload_transcript_to_s3


@pytest.mark.asyncio
async def test_upload_audio_to_s3_success():
    """Test successful audio upload to S3."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(b"fake audio data")
        temp_path = tf.name

    try:
        # Mock dependencies
        mock_ctx = AsyncMock()
        mock_s3_fs = AsyncMock()
        mock_db_client = AsyncMock()

        with (
            patch("api.tasks.s3_upload.s3_fs", mock_s3_fs),
            patch("api.tasks.s3_upload.db_client", mock_db_client),
        ):
            await upload_audio_to_s3(
                mock_ctx, workflow_run_id=123, temp_file_path=temp_path
            )

            # Verify S3 upload was called
            mock_s3_fs.aupload_file.assert_called_once_with(
                temp_path, "recordings/123.wav"
            )

            # Verify DB update was called
            mock_db_client.update_workflow_run.assert_called_once_with(
                run_id=123, recording_url="recordings/123.wav"
            )

            # Verify temp file was cleaned up
            assert not os.path.exists(temp_path)

    finally:
        # Clean up if test failed
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_upload_audio_to_s3_file_not_found():
    """Test audio upload when temp file doesn't exist."""
    mock_ctx = AsyncMock()

    with pytest.raises(FileNotFoundError):
        await upload_audio_to_s3(
            mock_ctx, workflow_run_id=123, temp_file_path="/nonexistent/file.wav"
        )


@pytest.mark.asyncio
async def test_upload_transcript_to_s3_success():
    """Test successful transcript upload to S3."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
        tf.write("Test transcript content")
        temp_path = tf.name

    try:
        # Mock dependencies
        mock_ctx = AsyncMock()
        mock_s3_fs = AsyncMock()
        mock_db_client = AsyncMock()

        with (
            patch("api.tasks.s3_upload.s3_fs", mock_s3_fs),
            patch("api.tasks.s3_upload.db_client", mock_db_client),
        ):
            await upload_transcript_to_s3(
                mock_ctx, workflow_run_id=456, temp_file_path=temp_path
            )

            # Verify S3 upload was called
            mock_s3_fs.aupload_file.assert_called_once_with(
                temp_path, "transcripts/456.txt"
            )

            # Verify DB update was called
            mock_db_client.update_workflow_run.assert_called_once_with(
                run_id=456, transcript_url="transcripts/456.txt"
            )

            # Verify temp file was cleaned up
            assert not os.path.exists(temp_path)

    finally:
        # Clean up if test failed
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_upload_s3_cleanup_on_error():
    """Test that temp files are cleaned up even when S3 upload fails."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(b"fake audio data")
        temp_path = tf.name

    try:
        mock_ctx = AsyncMock()
        mock_s3_fs = AsyncMock()
        # Make S3 upload fail
        mock_s3_fs.aupload_file.side_effect = Exception("S3 upload failed")

        with patch("api.tasks.s3_upload.s3_fs", mock_s3_fs):
            with pytest.raises(Exception):
                await upload_audio_to_s3(
                    mock_ctx, workflow_run_id=123, temp_file_path=temp_path
                )

            # Verify temp file was still cleaned up
            assert not os.path.exists(temp_path)

    finally:
        # Clean up if test failed
        if os.path.exists(temp_path):
            os.remove(temp_path)
