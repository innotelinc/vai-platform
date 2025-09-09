import os

from loguru import logger
from pipecat.utils.context import set_current_run_id

from api.db import db_client
from api.services.storage import get_current_storage_backend, storage_fs


async def upload_audio_to_s3(ctx, workflow_run_id: int, temp_file_path: str):
    """Upload audio file from temp path to S3."""
    run_id = str(workflow_run_id)
    set_current_run_id(run_id)

    logger.info(f"Starting audio upload to S3 from {temp_file_path}")

    try:
        # Verify temp file exists
        if not os.path.exists(temp_file_path):
            logger.error(f"Temp audio file not found: {temp_file_path}")
            raise FileNotFoundError(f"Temp audio file not found: {temp_file_path}")

        file_size = os.path.getsize(temp_file_path)
        logger.debug(f"Audio file size: {file_size} bytes")

        recording_url = f"recordings/{workflow_run_id}.wav"
        storage_backend = get_current_storage_backend()

        logger.info(
            f"UPLOAD: Using {storage_backend.name} (value: {storage_backend.value}) for audio upload - workflow_run_id: {workflow_run_id}"
        )

        await storage_fs.aupload_file(temp_file_path, recording_url)

        # Update DB with recording URL and storage backend
        await db_client.update_workflow_run(
            run_id=workflow_run_id,
            recording_url=recording_url,
            storage_backend=storage_backend.value,
        )

        logger.info(
            f"Successfully uploaded audio to {storage_backend.name}: {recording_url} (stored backend: {storage_backend.name})"
        )

    except Exception as e:
        logger.error(f"Error uploading audio to S3 for workflow {workflow_run_id}: {e}")
        raise
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.debug(f"Cleaned up temp audio file: {temp_file_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temp audio file {temp_file_path}: {e}"
                )


async def upload_transcript_to_s3(ctx, workflow_run_id: int, temp_file_path: str):
    """Upload transcript file from temp path to S3."""
    run_id = str(workflow_run_id)
    set_current_run_id(run_id)

    logger.info(f"Starting transcript upload to S3 from {temp_file_path}")

    try:
        # Verify temp file exists
        if not os.path.exists(temp_file_path):
            logger.error(f"Temp transcript file not found: {temp_file_path}")
            raise FileNotFoundError(f"Temp transcript file not found: {temp_file_path}")

        file_size = os.path.getsize(temp_file_path)
        logger.debug(f"Transcript file size: {file_size} bytes")

        transcript_url = f"transcripts/{workflow_run_id}.txt"
        storage_backend = get_current_storage_backend()

        logger.info(
            f"UPLOAD: Using {storage_backend.name} (value: {storage_backend.value}) for transcript upload - workflow_run_id: {workflow_run_id}"
        )

        await storage_fs.aupload_file(temp_file_path, transcript_url)

        # Update DB with transcript URL and storage backend
        await db_client.update_workflow_run(
            run_id=workflow_run_id,
            transcript_url=transcript_url,
            storage_backend=storage_backend.value,
        )

        logger.info(
            f"Successfully uploaded transcript to {storage_backend.name}: {transcript_url} (stored backend: {storage_backend.name})"
        )

    except Exception as e:
        logger.error(
            f"Error uploading transcript to S3 for workflow {workflow_run_id}: {e}"
        )
        raise
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.debug(f"Cleaned up temp transcript file: {temp_file_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temp transcript file {temp_file_path}: {e}"
                )


async def upload_voicemail_audio_to_s3(
    ctx,
    workflow_run_id: int,
    temp_file_path: str,
    s3_key: str,
):
    """Upload voicemail detection audio from temp file to S3.

    This function is similar to upload_audio_to_s3 but handles voicemail-specific
    paths and doesn't update the workflow run's recording_url field.

    Args:
        ctx: ARQ context
        workflow_run_id: The workflow run ID
        temp_file_path: Path to the temporary WAV file
        s3_key: The S3 key where the file should be uploaded
    """
    run_id = str(workflow_run_id)
    set_current_run_id(run_id)

    logger.info(f"Starting voicemail audio upload to S3 from {temp_file_path}")

    try:
        # Verify temp file exists
        if not os.path.exists(temp_file_path):
            logger.error(f"Temp voicemail audio file not found: {temp_file_path}")
            raise FileNotFoundError(
                f"Temp voicemail audio file not found: {temp_file_path}"
            )

        file_size = os.path.getsize(temp_file_path)
        logger.debug(f"Voicemail audio file size: {file_size} bytes")

        # Upload to S3
        upload_ok = await storage_fs.aupload_file(temp_file_path, s3_key)

        if upload_ok:
            logger.info(f"Successfully uploaded voicemail audio to S3: {s3_key}")
        else:
            logger.error(
                f"Failed to upload voicemail audio to S3 for workflow {workflow_run_id}"
            )
            raise Exception(f"S3 upload failed for {s3_key}")

    except Exception as e:
        logger.error(
            f"Error uploading voicemail audio to S3 for workflow {workflow_run_id}: {e}"
        )
        raise
    finally:
        # Clean up temp file (same pattern as upload_audio_to_s3)
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.debug(f"Cleaned up temp voicemail audio file: {temp_file_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temp voicemail audio file {temp_file_path}: {e}"
                )
