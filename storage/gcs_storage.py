"""
Google Cloud Storage Integration Module

Handles uploading and downloading datasets and adapters to/from GCS.
Provides multi-tenant isolation through bucket path prefixes.
"""

import os
import json
import logging
from typing import Optional, Dict, List, Union, BinaryIO
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class GCSStorage:
    """
    Google Cloud Storage client for multi-tenant dataset storage.
    
    Organizes data in buckets with the following structure:
    gs://{bucket}/users/{user_id}/datasets/{dataset_id}/raw/
    gs://{bucket}/users/{user_id}/datasets/{dataset_id}/processed/
    gs://{bucket}/users/{user_id}/adapters/{adapter_id}/
    """
    
    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None,
    ):
        """
        Initialize GCS storage client.
        
        Args:
            bucket_name: GCS bucket name
            credentials_path: Path to service account JSON (optional, uses default if not provided)
        """
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self._client = None
        self._bucket = None
    
    @property
    def client(self):
        """Lazy-load GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage
                
                if self.credentials_path:
                    self._client = storage.Client.from_service_account_json(self.credentials_path)
                else:
                    # Use default credentials (GOOGLE_APPLICATION_CREDENTIALS env var)
                    self._client = storage.Client()
                    
                logger.info(f"GCS client initialized for bucket: {self.bucket_name}")
            except ImportError:
                raise ImportError("google-cloud-storage is required. Install with: pip install google-cloud-storage")
            except Exception as e:
                logger.error(f"Failed to initialize GCS client: {e}")
                raise
        return self._client
    
    @property
    def bucket(self):
        """Get the GCS bucket object."""
        if self._bucket is None:
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket
    
    def _get_user_path(self, user_id: str) -> str:
        """Get the base path for a user."""
        return f"users/{user_id}"
    
    def _get_dataset_path(self, user_id: str, dataset_id: str) -> str:
        """Get the base path for a dataset."""
        return f"{self._get_user_path(user_id)}/datasets/{dataset_id}"
    
    def _get_adapter_path(self, user_id: str, adapter_id: str) -> str:
        """Get the base path for an adapter."""
        return f"{self._get_user_path(user_id)}/adapters/{adapter_id}"
    
    # ==========================================================================
    # File Operations
    # ==========================================================================
    
    def upload_file(
        self,
        local_path: Union[str, Path],
        gcs_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file to GCS.
        
        Args:
            local_path: Local file path
            gcs_path: Destination path in bucket
            content_type: Optional MIME type
            
        Returns:
            GCS URI (gs://bucket/path)
        """
        blob = self.bucket.blob(gcs_path)
        
        if content_type:
            blob.content_type = content_type
        
        blob.upload_from_filename(str(local_path))
        
        uri = f"gs://{self.bucket_name}/{gcs_path}"
        logger.info(f"Uploaded {local_path} to {uri}")
        return uri
    
    def upload_from_string(
        self,
        content: Union[str, bytes],
        gcs_path: str,
        content_type: str = "application/json",
    ) -> str:
        """
        Upload string/bytes content directly to GCS.
        
        Args:
            content: String or bytes to upload
            gcs_path: Destination path in bucket
            content_type: MIME type
            
        Returns:
            GCS URI
        """
        blob = self.bucket.blob(gcs_path)
        blob.content_type = content_type
        
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        blob.upload_from_string(
            content,
            content_type=content_type
        )
        
        uri = f"gs://{self.bucket_name}/{gcs_path}"
        logger.info(f"Uploaded content to {uri}")
        return uri
    
    def download_file(self, gcs_path: str, local_path: Union[str, Path]) -> str:
        """
        Download a file from GCS.
        
        Args:
            gcs_path: Source path in bucket
            local_path: Local destination path
            
        Returns:
            Local file path
        """
        blob = self.bucket.blob(gcs_path)
        
        # Ensure local directory exists
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        blob.download_to_filename(str(local_path))
        
        logger.info(f"Downloaded gs://{self.bucket_name}/{gcs_path} to {local_path}")
        return str(local_path)
    
    def download_as_string(self, gcs_path: str) -> bytes:
        """Download file content as bytes."""
        blob = self.bucket.blob(gcs_path)
        return blob.download_as_bytes()
    
    def download_as_json(self, gcs_path: str) -> Dict:
        """Download and parse JSON file."""
        content = self.download_as_string(gcs_path)
        return json.loads(content.decode('utf-8'))
    
    def delete_file(self, gcs_path: str) -> bool:
        """Delete a file from GCS."""
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"Deleted gs://{self.bucket_name}/{gcs_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {gcs_path}: {e}")
            return False
    
    def exists(self, gcs_path: str) -> bool:
        """Check if a file exists in GCS."""
        blob = self.bucket.blob(gcs_path)
        return blob.exists()
    
    def list_files(self, prefix: str) -> List[str]:
        """List all files under a prefix."""
        blobs = self.bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]
    
    # ==========================================================================
    # Directory Operations
    # ==========================================================================
    
    def upload_directory(
        self,
        local_dir: Union[str, Path],
        gcs_prefix: str,
    ) -> List[str]:
        """
        Upload an entire directory to GCS.
        
        Args:
            local_dir: Local directory path
            gcs_prefix: Destination prefix in bucket
            
        Returns:
            List of uploaded GCS URIs
        """
        local_dir = Path(local_dir)
        uploaded = []
        
        for local_path in local_dir.rglob("*"):
            if local_path.is_file():
                relative_path = local_path.relative_to(local_dir)
                gcs_path = f"{gcs_prefix}/{relative_path}".replace("\\", "/")
                
                uri = self.upload_file(local_path, gcs_path)
                uploaded.append(uri)
        
        return uploaded
    
    def download_directory(
        self,
        gcs_prefix: str,
        local_dir: Union[str, Path],
    ) -> List[str]:
        """
        Download all files under a prefix to a local directory.
        
        Args:
            gcs_prefix: Source prefix in bucket
            local_dir: Local destination directory
            
        Returns:
            List of downloaded local paths
        """
        local_dir = Path(local_dir)
        downloaded = []
        
        for blob_name in self.list_files(gcs_prefix):
            relative_path = blob_name[len(gcs_prefix):].lstrip("/")
            local_path = local_dir / relative_path
            
            self.download_file(blob_name, local_path)
            downloaded.append(str(local_path))
        
        return downloaded
    
    def delete_directory(self, prefix: str) -> int:
        """
        Delete all files under a prefix.
        
        Returns:
            Number of files deleted
        """
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        count = 0
        
        for blob in blobs:
            try:
                blob.delete()
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete {blob.name}: {e}")
        
        logger.info(f"Deleted {count} files under {prefix}")
        return count
    
    # ==========================================================================
    # Dataset Operations
    # ==========================================================================
    
    def upload_dataset(
        self,
        user_id: str,
        dataset_id: str,
        local_dir: Union[str, Path],
    ) -> Dict[str, str]:
        """
        Upload a processed dataset to GCS.
        
        Args:
            user_id: User ID for tenant isolation
            dataset_id: Dataset ID
            local_dir: Local directory with processed dataset files
            
        Returns:
            Dict with GCS paths for each uploaded file type
        """
        base_path = self._get_dataset_path(user_id, dataset_id)
        local_dir = Path(local_dir)
        
        paths = {}
        
        # Upload each file in the dataset directory
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(local_dir)
                gcs_path = f"{base_path}/{relative}".replace("\\", "/")
                uri = self.upload_file(file_path, gcs_path)
                paths[str(relative)] = uri
        
        logger.info(f"Uploaded dataset {dataset_id} for user {user_id}")
        return paths
    
    def download_dataset(
        self,
        user_id: str,
        dataset_id: str,
        local_dir: Union[str, Path],
    ) -> str:
        """
        Download a dataset from GCS.
        
        Args:
            user_id: User ID
            dataset_id: Dataset ID
            local_dir: Local directory to download to
            
        Returns:
            Local directory path
        """
        base_path = self._get_dataset_path(user_id, dataset_id)
        self.download_directory(base_path, local_dir)
        return str(local_dir)
    
    def delete_dataset(self, user_id: str, dataset_id: str) -> int:
        """Delete a dataset from GCS."""
        base_path = self._get_dataset_path(user_id, dataset_id)
        return self.delete_directory(base_path)
    
    def get_dataset_gcs_path(self, user_id: str, dataset_id: str) -> str:
        """Get the GCS URI for a dataset."""
        base_path = self._get_dataset_path(user_id, dataset_id)
        return f"gs://{self.bucket_name}/{base_path}"
    
    def get_raw_path(self, user_id: str, dataset_id: str) -> str:
        """Get the GCS path for raw dataset files."""
        return f"{self._get_dataset_path(user_id, dataset_id)}/raw"
    
    def get_processed_path(self, user_id: str, dataset_id: str) -> str:
        """Get the GCS path for processed dataset files."""
        return f"{self._get_dataset_path(user_id, dataset_id)}/processed"
    
    def upload_raw_file(
        self,
        user_id: str,
        dataset_id: str,
        local_path: Union[str, Path],
        filename: Optional[str] = None,
    ) -> str:
        """
        Upload a raw dataset file to GCS.
        
        Args:
            user_id: User ID for tenant isolation
            dataset_id: Dataset ID
            local_path: Local file path to upload
            filename: Optional override for the filename in GCS
            
        Returns:
            GCS URI of the uploaded file
        """
        local_path = Path(local_path)
        filename = filename or local_path.name
        gcs_path = f"{self.get_raw_path(user_id, dataset_id)}/{filename}"
        
        return self.upload_file(local_path, gcs_path)
    
    def upload_raw_from_bytes(
        self,
        user_id: str,
        dataset_id: str,
        content: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload raw file content directly from bytes.
        
        Args:
            user_id: User ID
            dataset_id: Dataset ID
            content: File content as bytes
            filename: Filename to use in GCS
            content_type: Optional MIME type
            
        Returns:
            GCS URI of the uploaded file
        """
        gcs_path = f"{self.get_raw_path(user_id, dataset_id)}/{filename}"
        blob = self.bucket.blob(gcs_path)
        
        # Upload with content_type specified in the upload call
        # This ensures the content-type is set correctly in the upload request
        blob.upload_from_string(content, content_type=content_type or 'application/octet-stream')
        
        uri = f"gs://{self.bucket_name}/{gcs_path}"
        logger.info(f"Uploaded raw file to {uri}")
        return uri
    
    def download_raw_file(
        self,
        user_id: str,
        dataset_id: str,
        filename: str,
        local_path: Union[str, Path],
    ) -> str:
        """
        Download a raw dataset file from GCS.
        
        Args:
            user_id: User ID
            dataset_id: Dataset ID
            filename: Name of the file in GCS raw folder
            local_path: Local destination path
            
        Returns:
            Local file path
        """
        gcs_path = f"{self.get_raw_path(user_id, dataset_id)}/{filename}"
        return self.download_file(gcs_path, local_path)
    
    def list_raw_files(self, user_id: str, dataset_id: str) -> List[str]:
        """List all files in the raw folder for a dataset."""
        prefix = f"{self.get_raw_path(user_id, dataset_id)}/"
        return self.list_files(prefix)
    
    def upload_processed_files(
        self,
        user_id: str,
        dataset_id: str,
        local_dir: Union[str, Path],
    ) -> Dict[str, str]:
        """
        Upload processed dataset files to GCS.
        
        Args:
            user_id: User ID
            dataset_id: Dataset ID
            local_dir: Local directory with processed files
            
        Returns:
            Dict with relative paths as keys and GCS URIs as values
        """
        processed_path = self.get_processed_path(user_id, dataset_id)
        return {
            str(Path(local_path).relative_to(local_dir)): self.upload_file(
                local_path, 
                f"{processed_path}/{Path(local_path).relative_to(local_dir)}".replace("\\", "/")
            )
            for local_path in Path(local_dir).rglob("*") if local_path.is_file()
        }
    
    def save_metadata(
        self,
        user_id: str,
        dataset_id: str,
        metadata: Dict,
        filename: str = "pipeline_metadata.json",
    ) -> str:
        """
        Save metadata JSON to GCS dataset folder.
        
        Args:
            user_id: User ID
            dataset_id: Dataset ID
            metadata: Metadata dict to save
            filename: Metadata filename
            
        Returns:
            GCS URI
        """
        gcs_path = f"{self._get_dataset_path(user_id, dataset_id)}/{filename}"
        content = json.dumps(metadata, indent=2)
        return self.upload_from_string(content, gcs_path, "application/json")
    
    def get_metadata(
        self,
        user_id: str,
        dataset_id: str,
        filename: str = "pipeline_metadata.json",
    ) -> Optional[Dict]:
        """
        Get metadata JSON from GCS dataset folder.
        
        Args:
            user_id: User ID
            dataset_id: Dataset ID
            filename: Metadata filename
            
        Returns:
            Metadata dict or None if not found
        """
        gcs_path = f"{self._get_dataset_path(user_id, dataset_id)}/{filename}"
        try:
            return self.download_as_json(gcs_path)
        except Exception:
            return None
    
    # ==========================================================================
    # Adapter Operations
    # ==========================================================================
    
    def upload_adapter(
        self,
        user_id: str,
        adapter_id: str,
        local_dir: Union[str, Path],
    ) -> Dict[str, str]:
        """Upload a LoRA adapter to GCS."""
        base_path = self._get_adapter_path(user_id, adapter_id)
        local_dir = Path(local_dir)
        
        paths = {}
        
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(local_dir)
                gcs_path = f"{base_path}/{relative}".replace("\\", "/")
                uri = self.upload_file(file_path, gcs_path)
                paths[str(relative)] = uri
        
        logger.info(f"Uploaded adapter {adapter_id} for user {user_id}")
        return paths
    
    def download_adapter(
        self,
        user_id: str,
        adapter_id: str,
        local_dir: Union[str, Path],
    ) -> str:
        """Download an adapter from GCS."""
        base_path = self._get_adapter_path(user_id, adapter_id)
        self.download_directory(base_path, local_dir)
        return str(local_dir)
    
    def delete_adapter(self, user_id: str, adapter_id: str) -> int:
        """Delete an adapter from GCS."""
        base_path = self._get_adapter_path(user_id, adapter_id)
        return self.delete_directory(base_path)
    
    def get_adapter_gcs_path(self, user_id: str, adapter_id: str) -> str:
        """Get the GCS URI for an adapter."""
        base_path = self._get_adapter_path(user_id, adapter_id)
        return f"gs://{self.bucket_name}/{base_path}"


# Singleton instance (initialized when needed)
_gcs_storage: Optional[GCSStorage] = None


def get_gcs_storage(bucket_name: Optional[str] = None) -> GCSStorage:
    """
    Get or create the GCS storage instance.
    
    Args:
        bucket_name: GCS bucket name (uses env var GCS_BUCKET if not provided)
        
    Returns:
        GCSStorage instance
    """
    global _gcs_storage
    
    if _gcs_storage is None:
        bucket = bucket_name or os.getenv("GCS_BUCKET", "llm-platform-datasets")
        _gcs_storage = GCSStorage(bucket_name=bucket)
    
    return _gcs_storage
