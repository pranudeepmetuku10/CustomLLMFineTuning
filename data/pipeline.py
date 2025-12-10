"""
Dataset Pipeline Orchestrator

Combines file handling, preprocessing, splitting, and bias detection into a complete pipeline.
Supports both local storage and Google Cloud Storage (GCS) for multi-tenant isolation.
"""

import os
import json
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

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of running the data pipeline."""
    success: bool
    dataset_id: str
    user_id: str
    
    # Paths
    output_dir: str
    gcs_path: Optional[str] = None  # GCS URI if uploaded to cloud
    train_path: Optional[str] = None
    val_path: Optional[str] = None
    test_path: Optional[str] = None
    
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
    
    # Errors
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DatasetPipeline:
    """
    Complete data processing pipeline for user-uploaded datasets.
    
    Steps:
    1. Process upload (ZIP or JSON)
    2. Clean code
    3. Remove PII
    4. Deduplicate
    5. Run bias detection
    6. Split into train/val/test
    7. Save to local directory
    8. Upload to GCS (if configured)
    """
    
    def __init__(
        self,
        base_output_dir: str = "./data/users",
        train_ratio: float = 0.85,
        val_ratio: float = 0.10,
        test_ratio: float = 0.05,
        gcs_bucket: Optional[str] = None,
        use_gcs: bool = False,
    ):
        self.base_output_dir = Path(base_output_dir)
        self.gcs_bucket = gcs_bucket or os.getenv("GCS_DATASETS_BUCKET")
        self.use_gcs = use_gcs or (self.gcs_bucket is not None and os.getenv("USE_GCS", "false").lower() == "true")
        
        # Initialize GCS storage if configured
        self._gcs_storage = None
        if self.use_gcs and self.gcs_bucket:
            try:
                from storage.gcs_storage import GCSStorage
                self._gcs_storage = GCSStorage(bucket_name=self.gcs_bucket)
                logger.info(f"GCS storage enabled: {self.gcs_bucket}")
            except Exception as e:
                logger.warning(f"Failed to initialize GCS storage: {e}")
                self._gcs_storage = None
        
        # Initialize components
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
    
    def get_user_dataset_dir(self, user_id: str, dataset_id: str) -> Path:
        """Get the output directory for a user's dataset."""
        return self.base_output_dir / user_id / "datasets" / dataset_id
    
    def process(
        self,
        user_id: str,
        dataset_id: str,
        upload_path: str,
        dataset_name: Optional[str] = None,
    ) -> PipelineResult:
        """
        Run the complete pipeline on an uploaded file.
        
        Args:
            user_id: User's ID
            dataset_id: Unique dataset ID
            upload_path: Path to uploaded file (ZIP or JSON)
            dataset_name: Optional name for the dataset
            
        Returns:
            PipelineResult with all processing information
        """
        output_dir = self.get_user_dataset_dir(user_id, dataset_id)
        
        result = PipelineResult(
            success=False,
            dataset_id=dataset_id,
            user_id=user_id,
            output_dir=str(output_dir),
        )
        
        try:
            # Step 1: Process upload
            print(f"[Pipeline] Processing upload: {upload_path}")
            samples, upload_metadata = self.file_handler.process_upload(upload_path)
            result.input_samples = len(samples)
            
            if not samples:
                result.error = "No valid code samples found in upload"
                return result
            
            print(f"[Pipeline] Extracted {len(samples)} samples")
            
            # Step 2-4: Preprocess (clean, PII, dedup)
            print("[Pipeline] Running preprocessing...")
            processed_samples, process_stats = self.preprocessor.process_samples(samples)
            
            result.output_samples = len(processed_samples)
            result.duplicates_removed = process_stats.get("duplicates_removed", 0)
            result.pii_found = process_stats.get("pii_found", {})
            result.languages = process_stats.get("languages", {})
            
            if not processed_samples:
                result.error = "All samples filtered out during preprocessing"
                return result
            
            print(f"[Pipeline] {len(processed_samples)} samples after preprocessing")
            
            # Step 5: Run bias detection
            print("[Pipeline] Running bias detection...")
            bias_report = self.bias_detector.analyze(processed_samples, dataset_id)
            print(f"[Pipeline] Bias score: {bias_report.overall_bias_score:.2f} ({bias_report.overall_severity})")
            
            # Step 6: Split
            print("[Pipeline] Splitting dataset...")
            splits = self.splitter.split(processed_samples, stratify_by_language=True)
            
            result.train_count = len(splits['train'])
            result.val_count = len(splits['val'])
            result.test_count = len(splits['test'])
            
            # Step 7: Save
            print(f"[Pipeline] Saving to {output_dir}")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save raw upload copy
            raw_dir = output_dir / "raw"
            raw_dir.mkdir(exist_ok=True)
            raw_copy = raw_dir / Path(upload_path).name
            shutil.copy2(upload_path, raw_copy)
            
            # Save processed splits
            processed_dir = output_dir / "processed"
            file_paths = self.splitter.save_splits(splits, str(processed_dir))
            
            result.train_path = file_paths.get('train')
            result.val_path = file_paths.get('val')
            result.test_path = file_paths.get('test')
            
            # Save bias report
            bias_report_path = output_dir / "bias_report.json"
            self.bias_detector.save_report(bias_report, str(bias_report_path))
            
            # Prepare GCS path
            gcs_path = None
            if self._gcs_storage:
                gcs_path = self._gcs_storage.get_dataset_gcs_path(user_id, dataset_id)
            
            # Save pipeline metadata
            pipeline_metadata = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "dataset_name": dataset_name or dataset_id,
                "created_at": datetime.utcnow().isoformat(),
                "upload_metadata": upload_metadata,
                "processing_stats": process_stats,
                "split_stats": self.splitter.get_split_stats(splits),
                "bias_summary": {
                    "overall_score": bias_report.overall_bias_score,
                    "severity": bias_report.overall_severity,
                    "recommendations": bias_report.recommendations,
                },
                "gcs_path": gcs_path,
                "storage_type": "gcs" if gcs_path else "local",
            }
            
            with open(output_dir / "pipeline_metadata.json", 'w') as f:
                json.dump(pipeline_metadata, f, indent=2)
            
            # Step 8: Upload to GCS if configured
            if self._gcs_storage:
                print(f"[Pipeline] Uploading to GCS: {gcs_path}")
                try:
                    gcs_files = self._gcs_storage.upload_dataset(user_id, dataset_id, output_dir)
                    result.gcs_path = gcs_path
                    print(f"[Pipeline] Uploaded {len(gcs_files)} files to GCS")
                except Exception as e:
                    logger.error(f"GCS upload failed: {e}")
                    print(f"[Pipeline] Warning: GCS upload failed: {e}")
                    # Don't fail the pipeline, just log the error
            
            result.success = True
            print(f"[Pipeline] Complete! Train: {result.train_count}, Val: {result.val_count}, Test: {result.test_count}")
            
        except Exception as e:
            result.error = str(e)
            print(f"[Pipeline] Error: {e}")
        
        return result
    
    def get_dataset_info(self, user_id: str, dataset_id: str) -> Optional[Dict]:
        """Get metadata for an existing dataset."""
        output_dir = self.get_user_dataset_dir(user_id, dataset_id)
        metadata_path = output_dir / "pipeline_metadata.json"
        
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r') as f:
            return json.load(f)
    
    def delete_dataset(self, user_id: str, dataset_id: str) -> bool:
        """Delete a user's dataset from local storage and GCS."""
        deleted_local = False
        deleted_gcs = False
        
        # Delete from local storage
        output_dir = self.get_user_dataset_dir(user_id, dataset_id)
        if output_dir.exists():
            shutil.rmtree(output_dir)
            deleted_local = True
        
        # Delete from GCS if configured
        if self._gcs_storage:
            try:
                count = self._gcs_storage.delete_dataset(user_id, dataset_id)
                deleted_gcs = count > 0
                logger.info(f"Deleted {count} files from GCS for dataset {dataset_id}")
            except Exception as e:
                logger.error(f"Failed to delete from GCS: {e}")
        
        return deleted_local or deleted_gcs
    
    def list_user_datasets(self, user_id: str) -> List[Dict]:
        """List all datasets for a user."""
        user_dir = self.base_output_dir / user_id / "datasets"
        
        if not user_dir.exists():
            return []
        
        datasets = []
        for dataset_dir in user_dir.iterdir():
            if dataset_dir.is_dir():
                info = self.get_dataset_info(user_id, dataset_dir.name)
                if info:
                    datasets.append({
                        "dataset_id": dataset_dir.name,
                        "name": info.get("dataset_name", dataset_dir.name),
                        "created_at": info.get("created_at"),
                        "samples": info.get("processing_stats", {}).get("output_count", 0),
                    })
        
        return datasets
    
    def get_bias_report(self, user_id: str, dataset_id: str) -> Optional[Dict]:
        """Get bias report for a dataset."""
        output_dir = self.get_user_dataset_dir(user_id, dataset_id)
        bias_report_path = output_dir / "bias_report.json"
        
        if not bias_report_path.exists():
            return None
        
        return self.bias_detector.load_report(str(bias_report_path))

