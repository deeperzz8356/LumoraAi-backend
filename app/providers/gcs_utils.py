"""
Google Cloud Storage utilities for downloading video files.
Handles GCS bucket operations and file management.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from google.cloud import storage

from app.core.credentials import load_vertex_credentials_from_settings


logger = logging.getLogger(__name__)


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    """
    Parse a GCS URI into bucket name and object path.
    
    Args:
        gcs_uri: GCS URI like 'gs://bucket-name/path/to/file.mp4'
        
    Returns:
        Tuple of (bucket_name, object_path)
    """
    match = re.match(r"gs://([^/]+)/(.*)", gcs_uri)
    if not match:
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    return match.group(1), match.group(2)


def _build_storage_client(project_id: str, credentials_path: Optional[str] = None) -> storage.Client:
    credentials = load_vertex_credentials_from_settings()
    return storage.Client(project=project_id, credentials=credentials)


async def download_video_from_gcs(
    gcs_uri: str,
    local_filepath: str,
    project_id: str,
    credentials_path: Optional[str] = None,
) -> str:
    """
    Download a video file from Google Cloud Storage to local disk.
    
    Args:
        gcs_uri: Full GCS URI (e.g., 'gs://bucket-name/video.mp4')
        local_filepath: Local path where file will be saved
        project_id: GCP project ID
        credentials_path: Optional path to credentials JSON
        
    Returns:
        Path to downloaded file
        
    Raises:
        ValueError: If GCS URI is invalid
        Exception: If download fails
    """
    try:
        bucket_name, object_path = parse_gcs_uri(gcs_uri)
        
        # Create local directory if it doesn't exist
        Path(local_filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Download in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def _download():
            client = _build_storage_client(project_id, credentials_path)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(object_path)
            blob.download_to_filename(local_filepath)
            return local_filepath
        
        result = await loop.run_in_executor(None, _download)
        logger.info(f"Downloaded video from GCS: {gcs_uri} -> {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to download video from GCS {gcs_uri}: {e}")
        raise


async def list_videos_in_gcs_folder(
    gcs_folder_uri: str,
    project_id: str,
    credentials_path: Optional[str] = None,
) -> list[str]:
    """
    List all video files in a GCS folder.
    
    Args:
        gcs_folder_uri: GCS folder URI (e.g., 'gs://bucket-name/folder/')
        project_id: GCP project ID
        credentials_path: Optional path to credentials JSON
        
    Returns:
        List of full GCS URIs for video files
    """
    try:
        bucket_name, folder_path = parse_gcs_uri(gcs_folder_uri.rstrip("/") + "/")
        
        def _list():
            client = _build_storage_client(project_id, credentials_path)
            bucket = client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=folder_path)
            
            video_files = []
            for blob in blobs:
                if blob.name.lower().endswith(('.mp4', '.webm', '.mov')):
                    video_files.append(f"gs://{bucket_name}/{blob.name}")
            return video_files
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _list)
        logger.info(f"Found {len(result)} videos in {gcs_folder_uri}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to list videos in GCS folder {gcs_folder_uri}: {e}")
        raise


async def upload_video_to_gcs(
    local_filepath: str,
    gcs_uri: str,
    project_id: str,
    credentials_path: Optional[str] = None,
) -> str:
    """
    Upload a local video file to Google Cloud Storage.
    
    Args:
        local_filepath: Path to local video file
        gcs_uri: Destination GCS URI
        project_id: GCP project ID
        credentials_path: Optional path to credentials JSON
        
    Returns:
        Full GCS URI of uploaded file
    """
    try:
        bucket_name, object_path = parse_gcs_uri(gcs_uri)
        
        def _upload():
            client = _build_storage_client(project_id, credentials_path)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(object_path)
            blob.upload_from_filename(local_filepath)
            return f"gs://{bucket_name}/{object_path}"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _upload)
        logger.info(f"Uploaded video to GCS: {local_filepath} -> {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to upload video to GCS {gcs_uri}: {e}")
        raise


def delete_gcs_file(
    gcs_uri: str,
    project_id: str,
    credentials_path: Optional[str] = None,
) -> bool:
    """
    Delete a file from Google Cloud Storage.
    
    Args:
        gcs_uri: GCS URI of file to delete
        project_id: GCP project ID
        credentials_path: Optional path to credentials JSON
        
    Returns:
        True if successful
    """
    try:
        bucket_name, object_path = parse_gcs_uri(gcs_uri)
        client = _build_storage_client(project_id, credentials_path)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_path)
        blob.delete()
        logger.info(f"Deleted GCS file: {gcs_uri}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete GCS file {gcs_uri}: {e}")
        return False
