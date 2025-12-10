"""
Tenant Storage Manager

Handles per-tenant data isolation for datasets and adapters in GCS and locally.
"""

import os
from typing import Optional, List
from pathlib import Path
from google.cloud import storage
from google.cloud.exceptions import NotFound
from dotenv import load_dotenv

load_dotenv()


class TenantStorageManager:
    """
    Manages tenant-isolated storage for datasets and adapters.
    
    Supports both Google Cloud Storage (production) and local filesystem (development).
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        
        # GCS Configuration
        self.gcs_project = os.getenv("GCS_PROJECT")
        self.datasets_bucket = os.getenv("GCS_DATASETS_BUCKET")
        self.adapters_bucket = os.getenv("GCS_ADAPTERS_BUCKET")
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # Local storage paths
        self.local_base_path = Path("./data/users") / user_id
        
        # Initialize GCS client if credentials available
        self._gcs_client = None
    
    @property
    def gcs_client(self) -> Optional[storage.Client]:
        """Lazy-load GCS client."""
        if self._gcs_client is None and self.credentials_path:
            try:
                self._gcs_client = storage.Client.from_service_account_json(
                    self.credentials_path
                )
            except Exception as e:
                print(f"Warning: Could not initialize GCS client: {e}")
        return self._gcs_client
    
    # =========================================================================
    # Path Helpers
    # =========================================================================
    
    def get_dataset_gcs_path(self, dataset_id: str) -> str:
        """Get GCS path for a user's dataset."""
        return f"gs://{self.datasets_bucket}/users/{self.user_id}/datasets/{dataset_id}/"
    
    def get_adapter_gcs_path(self, adapter_id: str) -> str:
        """Get GCS path for a user's adapter."""
        return f"gs://{self.adapters_bucket}/users/{self.user_id}/adapters/{adapter_id}/"
    
    def get_dataset_local_path(self, dataset_id: str) -> Path:
        """Get local path for a user's dataset."""
        return self.local_base_path / "datasets" / dataset_id
    
    def get_adapter_local_path(self, adapter_id: str) -> Path:
        """Get local path for a user's adapter."""
        return self.local_base_path / "adapters" / adapter_id
    
    # =========================================================================
    # Directory Management
    # =========================================================================
    
    def ensure_local_directories(self) -> None:
        """Create local directory structure for user."""
        (self.local_base_path / "datasets").mkdir(parents=True, exist_ok=True)
        (self.local_base_path / "adapters").mkdir(parents=True, exist_ok=True)
    
    def create_dataset_directory(self, dataset_id: str, use_gcs: bool = False) -> str:
        """
        Create a new dataset directory for the user.
        
        Returns the path (GCS or local).
        """
        if use_gcs and self.gcs_client:
            # GCS doesn't need explicit directory creation
            return self.get_dataset_gcs_path(dataset_id)
        else:
            local_path = self.get_dataset_local_path(dataset_id)
            local_path.mkdir(parents=True, exist_ok=True)
            return str(local_path)
    
    def create_adapter_directory(self, adapter_id: str, use_gcs: bool = False) -> str:
        """
        Create a new adapter directory for the user.
        
        Returns the path (GCS or local).
        """
        if use_gcs and self.gcs_client:
            return self.get_adapter_gcs_path(adapter_id)
        else:
            local_path = self.get_adapter_local_path(adapter_id)
            local_path.mkdir(parents=True, exist_ok=True)
            return str(local_path)
    
    # =========================================================================
    # File Operations
    # =========================================================================
    
    def upload_file_to_gcs(
        self, 
        local_file_path: str, 
        bucket_name: str,
        destination_blob_name: str
    ) -> str:
        """
        Upload a file to GCS.
        
        Returns the GCS URI.
        """
        if not self.gcs_client:
            raise RuntimeError("GCS client not initialized")
        
        bucket = self.gcs_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        
        return f"gs://{bucket_name}/{destination_blob_name}"
    
    def download_file_from_gcs(
        self,
        bucket_name: str,
        source_blob_name: str,
        local_file_path: str
    ) -> None:
        """Download a file from GCS."""
        if not self.gcs_client:
            raise RuntimeError("GCS client not initialized")
        
        bucket = self.gcs_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        
        # Ensure local directory exists
        Path(local_file_path).parent.mkdir(parents=True, exist_ok=True)
        
        blob.download_to_filename(local_file_path)
    
    def list_gcs_files(self, bucket_name: str, prefix: str) -> List[str]:
        """List files in a GCS bucket with given prefix."""
        if not self.gcs_client:
            return []
        
        bucket = self.gcs_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        
        return [blob.name for blob in blobs]
    
    def delete_gcs_directory(self, bucket_name: str, prefix: str) -> int:
        """
        Delete all files in a GCS directory (prefix).
        
        Returns number of files deleted.
        """
        if not self.gcs_client:
            raise RuntimeError("GCS client not initialized")
        
        bucket = self.gcs_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        for blob in blobs:
            blob.delete()
        
        return len(blobs)
    
    # =========================================================================
    # Upload Helpers
    # =========================================================================
    
    def upload_dataset(
        self,
        dataset_id: str,
        local_files: List[str],
        use_gcs: bool = True
    ) -> str:
        """
        Upload dataset files to storage.
        
        Args:
            dataset_id: Unique dataset identifier
            local_files: List of local file paths to upload
            use_gcs: If True, upload to GCS; otherwise, copy to local storage
            
        Returns:
            Storage path (GCS URI or local path)
        """
        if use_gcs and self.gcs_client:
            base_path = f"users/{self.user_id}/datasets/{dataset_id}"
            
            for file_path in local_files:
                file_name = Path(file_path).name
                blob_name = f"{base_path}/{file_name}"
                self.upload_file_to_gcs(file_path, self.datasets_bucket, blob_name)
            
            return self.get_dataset_gcs_path(dataset_id)
        else:
            # Local storage
            dest_dir = self.get_dataset_local_path(dataset_id)
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            import shutil
            for file_path in local_files:
                shutil.copy2(file_path, dest_dir / Path(file_path).name)
            
            return str(dest_dir)
    
    def upload_adapter(
        self,
        adapter_id: str,
        adapter_dir: str,
        use_gcs: bool = True
    ) -> str:
        """
        Upload trained adapter to storage.
        
        Args:
            adapter_id: Unique adapter identifier
            adapter_dir: Local directory containing adapter files
            use_gcs: If True, upload to GCS
            
        Returns:
            Storage path (GCS URI or local path)
        """
        if use_gcs and self.gcs_client:
            base_path = f"users/{self.user_id}/adapters/{adapter_id}"
            adapter_path = Path(adapter_dir)
            
            for file_path in adapter_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(adapter_path)
                    blob_name = f"{base_path}/{relative_path}"
                    self.upload_file_to_gcs(str(file_path), self.adapters_bucket, blob_name)
            
            return self.get_adapter_gcs_path(adapter_id)
        else:
            # Local storage - just return the path
            return adapter_dir


def get_tenant_storage(user_id: str) -> TenantStorageManager:
    """Factory function to create TenantStorageManager."""
    return TenantStorageManager(user_id)
