from typing import Annotated, Any, Dict, Optional, TypedDict

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.db import db_client
from api.enums import StorageBackend
from api.services.auth.depends import get_user
from api.services.storage import get_storage_for_backend, storage_fs


class S3SignedUrlResponse(TypedDict):
    url: str
    expires_in: int


class FileMetadataResponse(TypedDict):
    key: str
    metadata: Optional[Dict[str, Any]]


router = APIRouter(prefix="/s3", tags=["s3"])


async def _validate_and_extract_workflow_run_id(
    key: str, allow_special_paths: bool = False
) -> Optional[int]:
    """Validate the S3 key format and extract workflow_run_id if present.

    Args:
        key: S3 object key
        allow_special_paths: If True, allows looptalk/voicemail paths

    Returns:
        workflow_run_id if found, None for special paths (when allowed)

    Raises:
        HTTPException: If key format is invalid
    """
    if key.startswith("transcripts/") and key.endswith(".txt"):
        run_id_str = key[len("transcripts/") : -4]  # strip prefix & suffix
    elif key.startswith("recordings/") and key.endswith(".wav"):
        run_id_str = key[len("recordings/") : -4]
    elif allow_special_paths and (
        key.startswith("looptalk/") or key.startswith("voicemail_detections/")
    ):
        # Allow looptalk and voicemail paths for debugging (only if explicitly allowed)
        return None  # Skip validation for these paths
    else:
        raise HTTPException(status_code=400, detail="Invalid key format")

    if not run_id_str.isdigit():
        raise HTTPException(status_code=400, detail="Invalid workflow_run_id in key")

    return int(run_id_str)


async def _authorize_and_get_workflow_run(
    run_id: Optional[int], user, require_workflow_run: bool = True
) -> Optional[Any]:
    """Authorize access to workflow run and retrieve it.

    Args:
        run_id: Workflow run ID (can be None for special paths)
        user: Current user from auth
        require_workflow_run: If True, raises exception when run not found

    Returns:
        WorkflowRunModel or None

    Raises:
        HTTPException: If access is denied
    """
    if run_id is None:
        return None

    workflow_run = None
    if not user.is_superuser:
        # Regular users: Use organization_id to check access (security constraint)
        workflow_run = await db_client.get_workflow_run(
            run_id, organization_id=user.selected_organization_id
        )
        if not workflow_run and require_workflow_run:
            raise HTTPException(
                status_code=403, detail="Access denied for this workflow run"
            )
    else:
        # Superusers: Use get_workflow_run_by_id (no user/org constraint needed)
        workflow_run = await db_client.get_workflow_run_by_id(run_id)

    return workflow_run


@router.get(
    "/signed-url",
    response_model=S3SignedUrlResponse,
    summary="Generate a signed S3 URL",
)
async def get_signed_url(
    key: Annotated[str, Query(description="S3 object key")],
    expires_in: int = 3600,
    inline: bool = False,
    user=Depends(get_user),
):
    """Return a short-lived signed URL for a transcript or recording file stored on S3.

    Access Control:
    * Superusers can request any key.
    * Regular users can only request resources belonging to **their** workflow runs.
    """

    # Validate key and extract workflow_run_id (don't allow special paths for signed URLs)
    run_id = await _validate_and_extract_workflow_run_id(key, allow_special_paths=False)
    if run_id is None:
        raise HTTPException(status_code=400, detail="Invalid key format")

    # Authorize and get workflow run
    workflow_run = await _authorize_and_get_workflow_run(run_id, user)

    # ------------------------------------------------------------------
    # 3. Generate the signed URL using the correct storage backend
    # ------------------------------------------------------------------
    try:
        # Use the storage backend recorded when the file was uploaded
        if (
            workflow_run
            and hasattr(workflow_run, "storage_backend")
            and workflow_run.storage_backend
        ):
            backend = workflow_run.storage_backend
            storage = get_storage_for_backend(backend)
            logger.info(
                f"DOWNLOAD: Using stored {backend} (value: {backend}) for signed URL generation - workflow_run_id: {run_id}, key: {key}"
            )
        else:
            # Fallback to current storage for legacy records without storage_backend
            storage = storage_fs
            current_backend = StorageBackend.get_current_backend()
            logger.warning(
                f"DOWNLOAD: No storage_backend found for workflow run {run_id}, falling back to current {current_backend.name} - key: {key}"
            )

        url = await storage.aget_signed_url(
            key, expiration=expires_in, force_inline=inline
        )
        if not url:
            raise HTTPException(status_code=500, detail="Failed to generate signed URL")

        # Log successful URL generation
        backend_info = (
            f"stored {backend}"
            if workflow_run
            and hasattr(workflow_run, "storage_backend")
            and workflow_run.storage_backend
            else f"current {StorageBackend.get_current_backend().name}"
        )
        logger.info(
            f"Successfully generated signed URL using {backend_info} - expires in {expires_in}s"
        )

        return {"url": url, "expires_in": expires_in}
    except ClientError as exc:
        logger.error(f"Error generating signed URL: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate signed URL")


@router.get(
    "/file-metadata",
    response_model=FileMetadataResponse,
    summary="Get file metadata for debugging",
)
async def get_file_metadata(
    key: Annotated[str, Query(description="S3 object key")],
    user=Depends(get_user),
):
    """Get file metadata including creation timestamp for debugging.

    Access Control:
    * Superusers can request any key.
    * Regular users can only request resources belonging to **their** workflow runs.
    """

    # Validate key and extract workflow_run_id (allow special paths for metadata)
    run_id = await _validate_and_extract_workflow_run_id(key, allow_special_paths=True)

    # Authorize and get workflow run (for special paths, run_id might be None)
    workflow_run = await _authorize_and_get_workflow_run(
        run_id, user, require_workflow_run=False
    )

    # ------------------------------------------------------------------
    # 3. Get file metadata using the correct storage backend
    # ------------------------------------------------------------------
    try:
        # Use the storage backend recorded when the file was uploaded
        if (
            workflow_run
            and hasattr(workflow_run, "storage_backend")
            and workflow_run.storage_backend
        ):
            backend = workflow_run.storage_backend
            storage = get_storage_for_backend(backend)
            logger.info(
                f"METADATA: Using stored {backend} for metadata request - key: {key}"
            )
        else:
            # Fallback to current storage for legacy records or looptalk/voicemail files
            storage = storage_fs
            current_backend = StorageBackend.get_current_backend()
            logger.warning(
                f"METADATA: No storage_backend found, using current {current_backend.name} for metadata request - key: {key}"
            )

        metadata = await storage.aget_file_metadata(key)
        return {"key": key, "metadata": metadata}
    except Exception as exc:
        logger.error(f"Error getting file metadata: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get file metadata")
