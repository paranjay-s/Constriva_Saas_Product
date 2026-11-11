"""
=============================================================================
Construtiva Files Management API Router
=============================================================================
File: app/modules/files/router.py
Purpose:
  Manages file uploads and signed URLs using Supabase Storage.
  Supports architectural blueprint PDFs, rendered raster PNGs, and interior photos.
  Tracks storage keys and file metadata in the 'public.files' table.
=============================================================================
"""

import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from app.core.supabase import get_supabase_client, upload_to_storage, ensure_storage_buckets
from app.core.security import get_current_user, AuthenticatedUser, clean_uuid

logger = logging.getLogger("construtiva.files")
router = APIRouter()


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file directly to Supabase Storage"
)
async def upload_file(
    file: UploadFile = File(..., description="Binary file (PDF, PNG, JPG) to upload"),
    kind: str = Form(
        "floor_plan_pdf",
        description="File kind: 'floor_plan_pdf', 'material_photo', 'generated_plan', 'plan_preview', 'report', 'other'"
    ),
    project_id: Optional[str] = Form(None, description="Optional associated project UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Uploads a file to the appropriate Supabase Storage bucket and creates a record in the 'files' table.

    Args:
        file (UploadFile): The binary file payload.
        kind (str): Classification ('floor_plan_pdf', 'material_photo', 'plan_preview', etc.).
        project_id (Optional[str]): Project ID to attach the file to.
        current_user (AuthenticatedUser): Authenticated user session.

    Returns:
        dict: File ID, storage key, file name, and status.
    """
    supabase = get_supabase_client()
    ensure_storage_buckets()

    # Determine destination bucket based on file classification
    bucket_name = "blueprints"
    if kind == "material_photo":
        bucket_name = "site-photos"
    elif kind in ("plan_preview", "raster_image"):
        bucket_name = "rasters"

    try:
        content_bytes = await file.read()
        file_size = len(content_bytes)

        # Sanitize project_id to avoid PostgreSQL 22P02 invalid UUID syntax errors (e.g. from Swagger placeholder 'string')
        clean_project_id = clean_uuid(project_id)
        if clean_project_id:
            try:
                chk = supabase.table("projects").select("id").eq("id", clean_project_id).execute()
                if not chk.data:
                    clean_project_id = None
            except Exception:
                clean_project_id = None

        # Generate unique storage key
        unique_id = str(uuid.uuid4())
        safe_filename = file.filename.replace(" ", "_") if file.filename else "upload"
        storage_path = f"{clean_project_id or current_user.id}/{unique_id}_{safe_filename}"

        # Upload file bytes to Supabase Storage bucket
        storage_key = upload_to_storage(
            bucket_name=bucket_name,
            file_path=storage_path,
            file_bytes=content_bytes,
            content_type=file.content_type or "application/octet-stream"
        )

        # Record file metadata in public.files table
        file_record = {
            "id": unique_id,
            "project_id": clean_project_id,
            "user_id": current_user.id,
            "kind": kind,
            "name": file.filename or "upload",
            "storage_key": storage_key,
            "mime_type": file.content_type or "application/octet-stream",
            "size_bytes": file_size,
            "status": "uploaded",
        }

        supabase.table("files").insert(file_record).execute()

        logger.info(f"File uploaded successfully: {storage_key} ({file_size} bytes)")
        return {
            "id": unique_id,
            "name": file.filename,
            "kind": kind,
            "storage_key": storage_key,
            "size_bytes": file_size,
            "status": "uploaded",
        }

    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {str(e)}"
        )


@router.get(
    "/{file_id}/signed-url",
    summary="Generate a temporary signed URL to download or view a private file"
)
async def get_file_signed_url(
    file_id: str,
    expires_in_seconds: int = 3600,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Creates a time-limited signed URL for secure download from Supabase Storage.

    Args:
        file_id (str): UUID of the file.
        expires_in_seconds (int): URL validity duration (default 3600s = 1 hour).
        current_user (AuthenticatedUser): Authenticated user.

    Returns:
        dict: Signed download URL.
    """
    supabase = get_supabase_client()

    clean_fid = clean_uuid(file_id)
    if not clean_fid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: '{file_id}' is not a valid file UUID."
        )

    # Query file record to determine bucket and path
    res = supabase.table("files").select("*").eq("id", clean_fid).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File record not found.")

    file_row = res.data[0]
    storage_key = file_row.get("storage_key", "")

    # Storage key format is 'bucket_name/path/to/file'
    parts = storage_key.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage key format.")

    bucket_name, file_path = parts[0], parts[1]

    try:
        signed_res = supabase.storage.from_(bucket_name).create_signed_url(
            path=file_path,
            expires_in=expires_in_seconds
        )
        return {
            "file_id": file_id,
            "name": file_row.get("name"),
            "signed_url": signed_res.get("signedURL") or signed_res.get("signedUrl"),
            "expires_in": expires_in_seconds,
        }
    except Exception as e:
        logger.error(f"Failed to generate signed URL for {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate signed URL: {str(e)}"
        )
