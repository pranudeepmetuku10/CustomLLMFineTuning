"""
Data module for dataset processing pipeline.

Supports both local storage and GCS-only storage modes.
"""

from data.file_handler import FileHandler, CodeSample
from data.preprocessing import DataPreprocessor, CodeCleaner, PIIRemover, Deduplicator
from data.splitter import DatasetSplitter
from data.pipeline import DatasetPipeline, PipelineResult
from data.gcs_pipeline import GCSOnlyPipeline, GCSPipelineResult, get_gcs_pipeline
from data.bias_detection import BiasDetector, BiasReport, BiasMetrics
from data.routes import router as data_router

__all__ = [
    # File handling
    "FileHandler",
    "CodeSample",
    # Preprocessing
    "DataPreprocessor",
    "CodeCleaner",
    "PIIRemover",
    "Deduplicator",
    # Splitting
    "DatasetSplitter",
    # Pipelines
    "DatasetPipeline",
    "PipelineResult",
    "GCSOnlyPipeline",
    "GCSPipelineResult",
    "get_gcs_pipeline",
    # Bias detection
    "BiasDetector",
    "BiasReport",
    "BiasMetrics",
    # Router
    "data_router",
]
