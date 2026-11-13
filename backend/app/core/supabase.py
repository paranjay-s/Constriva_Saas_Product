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


def get_supabase_client() -> Client:
    """
    Returns the singleton administrative Supabase client initialized with the Service Role Key.
    This client has administrative access to query tables and read/write storage buckets.
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
        logger.info("Supabase admin client initialized successfully.")
    return _supabase_client


def get_user_supabase_client(token: Optional[str] = None) -> Client:
    """
    Returns a Supabase client authenticated as the current user using their Bearer JWT.
    This ensures database queries run within the user's Row-Level Security (RLS) context
    where auth.uid() matches the logged-in user ID.
    Falls back to get_supabase_client() if token is absent, empty, or not a JWT.
    """
    if not token or token.strip().lower() in ("", "none", "null", "undefined"):
        return get_supabase_client()

    clean_token = token.strip()
    if clean_token.count(".") != 2:
        return get_supabase_client()

    try:
        anon_key = settings.supabase_anon_key or settings.supabase_service_role_key
        user_client = create_client(settings.supabase_url, anon_key)
        user_client.postgrest.auth(clean_token)
        return user_client
    except Exception as e:
        logger.debug(f"Could not initialize user-scoped Supabase client: {e}")
        return get_supabase_client()


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

