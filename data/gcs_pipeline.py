"""
GCS-Only Dataset Pipeline

A pipeline that processes datasets entirely in GCS without local storage.
Designed to work with Airflow DAG for automated processing.
"""

import os
import json
import tempfile
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from data.file_handler import FileHandler, CodeSample
from data.preprocessing import DataPreprocessor, CodeCleaner, PIIRemover, Deduplicator
from data.splitter import DatasetSplitter
from data.bias_detection import BiasDetector, BiasReport
from storage.gcs_storage import GCSStorage

logger = logging.getLogger(__name__)


@dataclass
class GCSPipelineResult:
    """Result of running the GCS-only data pipeline."""
    success: bool
    dataset_id: str
    user_id: str
    
    # GCS Paths
    gcs_raw_path: Optional[str] = None
    gcs_processed_path: Optional[str] = None
    gcs_metadata_path: Optional[str] = None
    
    # Statistics
    input_samples: int = 0
    output_samples: int = 0
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    
    # Processing stats
    duplicates_removed: int = 0
    pii_found: Dict = None
    languages: Dict = None
    
    # Bias summary
    bias_score: float = 0.0
    bias_severity: str = "low"
    
    # Errors
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class GCSOnlyPipeline:
    """
    Complete data processing pipeline that uses only GCS for storage.
    
    This pipeline:
    1. Downloads raw file from GCS to temp directory
    2. Processes the dataset (clean, PII, dedup, bias detection, split)
    3. Uploads processed files directly to GCS
    4. Cleans up temp files
    
    Designed for use with Airflow DAG for automated processing.
    """
    
    def __init__(
        self,
        gcs_bucket: Optional[str] = None,
        train_ratio: float = 0.85,
        val_ratio: float = 0.10,
        test_ratio: float = 0.05,
    ):
        """
        Initialize the GCS-only pipeline.
        
        Args:
            gcs_bucket: GCS bucket name (uses GCS_BUCKET env var if not provided)
            train_ratio: Ratio of samples for training set
            val_ratio: Ratio of samples for validation set
            test_ratio: Ratio of samples for test set
        """
        self.gcs_bucket = gcs_bucket or os.getenv("GCS_BUCKET")
        if not self.gcs_bucket:
            raise ValueError("GCS bucket must be provided or set in GCS_BUCKET env var")
        
        # Initialize GCS storage
        self._gcs_storage = GCSStorage(bucket_name=self.gcs_bucket)
        logger.info(f"GCS-only pipeline initialized with bucket: {self.gcs_bucket}")
        
        # Initialize processing components
        self.file_handler = FileHandler()
        self.preprocessor = DataPreprocessor(
            cleaner=CodeCleaner(),
            pii_remover=PIIRemover(),
            deduplicator=Deduplicator(),
        )
        self.splitter = DatasetSplitter(
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
        )
        self.bias_detector = BiasDetector()
    
    @property
    def gcs(self) -> GCSStorage:
        """Get the GCS storage instance."""
        return self._gcs_storage
    
    def process_from_gcs(
        self,
        user_id: str,
        dataset_id: str,
        dataset_name: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> GCSPipelineResult:
        """
        Process a dataset from GCS raw path.
        
        This method:
        1. Downloads the raw file(s) from GCS
        2. Processes them through the pipeline
        3. Uploads processed results to GCS
        4. Cleans up temp files
        
        Args:
            user_id: User ID for tenant isolation
            dataset_id: Dataset ID
            dataset_name: Optional name for the dataset
            user_email: User's email for notifications
            
        Returns:
            GCSPipelineResult with processing information
        """
        result = GCSPipelineResult(
            success=False,
            dataset_id=dataset_id,
            user_id=user_id,
        )
        
        # Create temp directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"dataset_{dataset_id}_")
        
        try:
            # Step 1: List and download raw files from GCS
            print(f"[GCS Pipeline] Downloading raw files for dataset {dataset_id}")
            raw_files = self._gcs_storage.list_raw_files(user_id, dataset_id)
            
            if not raw_files:
                result.error = "No raw files found in GCS"
                return result
            
            # Download the first raw file (typically there's one upload per dataset)
            raw_file_gcs = raw_files[0]
            filename = Path(raw_file_gcs).name
            local_raw_path = Path(temp_dir) / "raw" / filename
            local_raw_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._gcs_storage.download_file(raw_file_gcs, local_raw_path)
            result.gcs_raw_path = f"gs://{self.gcs_bucket}/{raw_file_gcs}"
            
            print(f"[GCS Pipeline] Downloaded: {filename}")
            
            # Step 2: Process upload
            print(f"[GCS Pipeline] Processing upload: {local_raw_path}")
            samples, upload_metadata = self.file_handler.process_upload(str(local_raw_path))
            result.input_samples = len(samples)
            
            if not samples:
                result.error = "No valid code samples found in upload"
                return result
            
            print(f"[GCS Pipeline] Extracted {len(samples)} samples")
            
            # Step 3: Preprocess (clean, PII, dedup)
            print("[GCS Pipeline] Running preprocessing...")
            processed_samples, process_stats = self.preprocessor.process_samples(samples)
            
            result.output_samples = len(processed_samples)
            result.duplicates_removed = process_stats.get("duplicates_removed", 0)
            result.pii_found = process_stats.get("pii_found", {})
            result.languages = process_stats.get("languages", {})
            
            if not processed_samples:
                result.error = "All samples filtered out during preprocessing"
                return result
            
            print(f"[GCS Pipeline] {len(processed_samples)} samples after preprocessing")
            
            # Step 4: Run bias detection
            print("[GCS Pipeline] Running bias detection...")
            bias_report = self.bias_detector.analyze(processed_samples, dataset_id)
            result.bias_score = bias_report.overall_bias_score
            result.bias_severity = bias_report.overall_severity
            print(f"[GCS Pipeline] Bias score: {result.bias_score:.2f} ({result.bias_severity})")
            
            # Step 5: Split
            print("[GCS Pipeline] Splitting dataset...")
            splits = self.splitter.split(processed_samples, stratify_by_language=True)
            
            result.train_count = len(splits['train'])
            result.val_count = len(splits['val'])
            result.test_count = len(splits['test'])
            
            # Step 6: Save to temp directory
            processed_dir = Path(temp_dir) / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            
            file_paths = self.splitter.save_splits(splits, str(processed_dir))
            
            # Save bias report
            bias_report_path = Path(temp_dir) / "bias_report.json"
            self.bias_detector.save_report(bias_report, str(bias_report_path))
            
            # Step 7: Upload processed files to GCS
            print(f"[GCS Pipeline] Uploading processed files to GCS...")
            
            # Upload processed splits
            uploaded_files = self._gcs_storage.upload_processed_files(
                user_id, dataset_id, processed_dir
            )
            result.gcs_processed_path = f"gs://{self.gcs_bucket}/{self._gcs_storage.get_processed_path(user_id, dataset_id)}"
            
            # Upload bias report
            bias_gcs_path = f"{self._gcs_storage._get_dataset_path(user_id, dataset_id)}/bias_report.json"
            self._gcs_storage.upload_file(bias_report_path, bias_gcs_path)
            
            print(f"[GCS Pipeline] Uploaded {len(uploaded_files) + 1} files to GCS")
            
            # Step 8: Save pipeline metadata to GCS
            pipeline_metadata = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "user_email": user_email,
                "dataset_name": dataset_name or dataset_id,
                "created_at": datetime.utcnow().isoformat(),
                "processed_at": datetime.utcnow().isoformat(),
                "upload_metadata": upload_metadata,
                "processing_stats": process_stats,
                "split_stats": self.splitter.get_split_stats(splits),
                "bias_summary": {
                    "overall_score": bias_report.overall_bias_score,
                    "severity": bias_report.overall_severity,
                    "recommendations": bias_report.recommendations,
                },
                "gcs_paths": {
                    "raw": result.gcs_raw_path,
                    "processed": result.gcs_processed_path,
                },
                "storage_type": "gcs_only",
            }
            
            metadata_uri = self._gcs_storage.save_metadata(user_id, dataset_id, pipeline_metadata)
            result.gcs_metadata_path = metadata_uri
            
            result.success = True
            print(f"[GCS Pipeline] Complete! Train: {result.train_count}, Val: {result.val_count}, Test: {result.test_count}")
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"GCS Pipeline error: {e}", exc_info=True)
            print(f"[GCS Pipeline] Error: {e}")
            
        finally:
            # Clean up temp directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"[GCS Pipeline] Cleaned up temp directory")
        
        return result
    
    def get_dataset_info(self, user_id: str, dataset_id: str) -> Optional[Dict]:
        """Get metadata for a dataset from GCS."""
        return self._gcs_storage.get_metadata(user_id, dataset_id)
    
    def get_bias_report(self, user_id: str, dataset_id: str) -> Optional[Dict]:
        """Get bias report for a dataset from GCS."""
        return self._gcs_storage.get_metadata(user_id, dataset_id, "bias_report.json")
    
    def delete_dataset(self, user_id: str, dataset_id: str) -> int:
        """Delete a dataset from GCS."""
        return self._gcs_storage.delete_dataset(user_id, dataset_id)
    
    def dataset_exists(self, user_id: str, dataset_id: str) -> bool:
        """Check if a dataset exists in GCS."""
        raw_files = self._gcs_storage.list_raw_files(user_id, dataset_id)
        return len(raw_files) > 0


# Singleton instance
_gcs_pipeline: Optional[GCSOnlyPipeline] = None


def get_gcs_pipeline(bucket_name: Optional[str] = None) -> GCSOnlyPipeline:
    """
    Get or create the GCS-only pipeline instance.
    
    Args:
        bucket_name: GCS bucket name (uses env var GCS_BUCKET if not provided)
        
    Returns:
        GCSOnlyPipeline instance
    """
    global _gcs_pipeline
    
    if _gcs_pipeline is None:
        _gcs_pipeline = GCSOnlyPipeline(gcs_bucket=bucket_name)
    
    return _gcs_pipeline
