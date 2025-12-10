"""
Storage Module

Provides storage backends for multi-tenant dataset and adapter storage.
Primary backend is Google Cloud Storage (GCS) for production.
"""

from storage.gcs_storage import GCSStorage, get_gcs_storage

__all__ = [
    "GCSStorage",
    "get_gcs_storage",
]
