"""
=============================================================================
Construtiva Supabase Client & Storage Provisioner
=============================================================================
File: app/core/supabase.py
Purpose:
  Provides the global Supabase administrative client using the Service Role Key.
  Manages initialization of required private storage buckets ('blueprints', 'rasters', 'site-photos')
  and provides utility functions for file uploads and signed URL generation.
=============================================================================
"""

import os
import time
import logging
from typing import Optional
import jwt
from supabase import create_client, Client
from app.core.config import settings

logger = logging.getLogger("construtiva.supabase")

_supabase_client: Optional[Client] = None

# Storage buckets required by Construtiva
REQUIRED_BUCKETS = ["blueprints", "rasters", "site-photos"]


def get_service_role_jwt() -> Optional[str]:
    """
    Returns or mints a valid JWT with role='service_role' to ensure PostgREST
    bypasses Row-Level Security (BYPASSRLS) across all tables.
    """
    if settings.supabase_service_role_key and settings.supabase_service_role_key.count(".") == 2:
        return settings.supabase_service_role_key

    if settings.supabase_jwt_secret:
        try:
            payload = {
                "role": "service_role",
                "iss": "supabase",
                "iat": int(time.time()) - 30,
                "exp": int(time.time()) + 10 * 365 * 24 * 3600,
            }
            return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
        except Exception as e:
            logger.debug(f"Could not mint service_role JWT: {e}")
    return None


def get_supabase_client() -> Client:
    """
    Returns the singleton Supabase client initialized with the Service Role Key.
    This client has full administrative access to query tables and read/write storage buckets.
    """
    global _supabase_client
    if _supabase_client is None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured in environment."
            )
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )

        # Ensure PostgREST sends a service_role JWT to bypass RLS policies
        service_jwt = get_service_role_jwt()
        if service_jwt:
            try:
                _supabase_client.postgrest.auth(service_jwt)
                logger.info("Supabase admin client initialized with service_role BYPASSRLS authorization.")
            except Exception as e:
                logger.debug(f"Could not set postgrest auth: {e}")
        else:
            logger.info("Supabase admin client initialized successfully.")
    return _supabase_client


def ensure_storage_buckets() -> None:
    """
    Checks if required Supabase Storage buckets exist ('blueprints', 'rasters', 'site-photos').
    Creates any missing buckets automatically with private access.
    """
    if os.environ.get("TESTING") == "1":
        logger.debug("Skipping storage bucket initialization in testing environment.")
        return

    client = get_supabase_client()
    try:
        existing_buckets = [b.name for b in client.storage.list_buckets()]
        for bucket_name in REQUIRED_BUCKETS:
            if bucket_name not in existing_buckets:
                logger.info(f"Creating missing Supabase Storage bucket: '{bucket_name}'...")
                client.storage.create_bucket(
                    bucket_name,
                    options={"public": False}
                )
                logger.info(f"Bucket '{bucket_name}' created successfully.")
            else:
                logger.debug(f"Bucket '{bucket_name}' already exists.")
    except Exception as e:
        logger.warning(f"Could not verify/create storage buckets (will retry on upload): {e}")


def upload_to_storage(bucket_name: str, file_path: str, file_bytes: bytes, content_type: str) -> str:
    """
    Uploads raw bytes to a specific Supabase Storage bucket.
    
    Args:
        bucket_name: Target bucket ('blueprints', 'rasters', 'site-photos').
        file_path: Internal path/key in the bucket (e.g. 'proj_123/original.pdf').
        file_bytes: Raw binary file content.
        content_type: MIME type of the file (e.g. 'application/pdf', 'image/png').

    Returns:
        The storage key/path of the uploaded file inside the bucket.
    """
    client = get_supabase_client()
    # Upload binary content (upsert allows re-uploading revised versions)
    client.storage.from_(bucket_name).upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"}
    )
    return f"{bucket_name}/{file_path}"

