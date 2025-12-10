"""
Dataset API Routes

Endpoints for uploading, managing, and retrieving user datasets.
Uses GCS-only storage mode - all datasets are stored in Google Cloud Storage.
"""

import os
import uuid
import tempfile
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from auth.database import get_db
from auth.models import User, Dataset
from auth.dependencies import get_current_user, get_tenant_context, TenantContext
from data.gcs_pipeline import GCSOnlyPipeline, get_gcs_pipeline
from storage.gcs_storage import GCSStorage, get_gcs_storage


router = APIRouter(prefix="/datasets", tags=["Datasets"])

# Initialize GCS-only pipeline
GCS_BUCKET = os.getenv("GCS_BUCKET", "llm-platform-datasets-llm-finetuning-480620")
USE_GCS = os.getenv("USE_GCS", "true").lower() == "true"

# Global pipeline instance (GCS-only mode)
_pipeline: Optional[GCSOnlyPipeline] = None
_gcs_storage: Optional[GCSStorage] = None


def get_pipeline() -> GCSOnlyPipeline:
    """Get or create the GCS-only pipeline instance."""
    global _pipeline
    if _pipeline is None and USE_GCS:
        _pipeline = GCSOnlyPipeline(gcs_bucket=GCS_BUCKET)
    return _pipeline


def get_storage() -> GCSStorage:
    """Get or create the GCS storage instance."""
    global _gcs_storage
    if _gcs_storage is None and USE_GCS:
        _gcs_storage = GCSStorage(bucket_name=GCS_BUCKET)
    return _gcs_storage


# =============================================================================
# Schemas
# =============================================================================

class DatasetResponse(BaseModel):
    """Dataset response schema."""
    id: str
    name: str
    description: Optional[str]
    gcs_path: str
    version: int
    num_samples: int
    languages: Optional[dict]
    is_processed: bool
    processing_status: str
    created_at: str
    
    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    """Response for listing datasets."""
    datasets: List[DatasetResponse]
    total: int


class DatasetUploadResponse(BaseModel):
    """Response after uploading a dataset."""
    dataset_id: str
    name: str
    status: str
    message: str
    samples_extracted: int
    samples_processed: int
    train_count: int
    val_count: int
    test_count: int
    languages: dict
    duplicates_removed: int


class DatasetStatsResponse(BaseModel):
    """Dataset statistics response."""
    dataset_id: str
    name: str
    total_samples: int
    train_samples: int
    val_samples: int
    test_samples: int
    languages: dict
    processing_status: str
    created_at: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a new dataset (ZIP or JSON file) to GCS and trigger processing.
    
    - **file**: ZIP file with code files OR JSON file with code snippets
    - **name**: Name for the dataset
    - **description**: Optional description
    
    Processing Flow (Direct Mode):
    1. Upload raw file directly to GCS
    2. Create database record with status="pending"
    3. Trigger background processing task immediately
    4. User receives email notification when complete or failed
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    suffix = file.filename.lower().split('.')[-1]
    if suffix not in ['zip', 'json']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .zip or .json file"
        )
    
    # Generate dataset ID
    dataset_id = str(uuid.uuid4())
    
    try:
        # Get GCS storage
        storage = get_storage()
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GCS storage not configured"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Determine content type
        content_type = "application/zip" if suffix == "zip" else "application/json"
        
        # Upload raw file to GCS
        gcs_uri = storage.upload_raw_from_bytes(
            user_id=current_user.id,
            dataset_id=dataset_id,
            content=file_content,
            filename=file.filename,
            content_type=content_type,
        )
        
        print(f"[Upload] Raw file uploaded to: {gcs_uri}")
        
        # Get the dataset GCS base path
        gcs_path = storage.get_dataset_gcs_path(current_user.id, dataset_id)
        
        # Create database record with pending status
        dataset = Dataset(
            id=dataset_id,
            user_id=current_user.id,
            name=name,
            description=description,
            gcs_path=gcs_path,
            num_samples=0,
            languages=None,
            is_processed=False,
            processing_status="pending",
        )
        
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)
        
        # Trigger background processing
        background_tasks.add_task(
            process_dataset_background,
            user_id=current_user.id,
            dataset_id=dataset_id,
            dataset_name=name,
            user_email=current_user.email,
        )
        
        # Return pending response
        return DatasetUploadResponse(
            dataset_id=dataset_id,
            name=name,
            status="pending",
            message="Dataset uploaded successfully. Processing started in background. You will receive an email when complete.",
            samples_extracted=0,
            samples_processed=0,
            train_count=0,
            val_count=0,
            test_count=0,
            languages={},
            duplicates_removed=0,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


async def process_dataset_background(
    user_id: str,
    dataset_id: str,
    dataset_name: str,
    user_email: str,
):
    """
    Background task to process dataset and send email notifications.
    """
    print(f"[Background] Starting processing for dataset {dataset_id}")
    
    try:
        # 1. Run Pipeline
        pipeline = get_pipeline()
        if not pipeline:
            print("[Background] Error: Pipeline not initialized")
            return
            
        result = pipeline.process_from_gcs(
            user_id=user_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            user_email=user_email,
        )
        
        # 2. Update Database
        from auth.database import async_session_maker
        from utils.email import send_email
        from utils.email_templates import (
            get_success_email_html,
            get_failure_email_html,
            get_success_email_subject,
            get_failure_email_subject,
        )
        
        async with async_session_maker() as session:
            # Fetch dataset
            stmt = select(Dataset).where(Dataset.id == dataset_id)
            db_result = await session.execute(stmt)
            dataset = db_result.scalar_one_or_none()
            
            if dataset:
                if result.success:
                    dataset.is_processed = True
                    dataset.processing_status = "completed"
                    dataset.num_samples = result.output_samples
                    dataset.languages = result.languages
                    if result.gcs_processed_path:
                        dataset.gcs_path = result.gcs_processed_path
                    
                    # Send Success Email
                    email_html = get_success_email_html(
                        user_name=user_email.split('@')[0], # reliable enough
                        dataset_name=dataset_name,
                        dataset_id=dataset_id,
                        stats=result.to_dict()
                    )
                    subject = get_success_email_subject(dataset_name)
                    send_email(user_email, subject, email_html)
                    
                else:
                    dataset.processing_status = "failed"
                    
                    # Send Failure Email
                    email_html = get_failure_email_html(
                        user_name=user_email.split('@')[0],
                        dataset_name=dataset_name,
                        dataset_id=dataset_id,
                        error_message=result.error or "Unknown error"
                    )
                    subject = get_failure_email_subject(dataset_name)
                    # Send to user
                    send_email(user_email, subject, email_html)
                    # Send to admin
                    from utils.email import ALERT_EMAIL
                    send_email(ALERT_EMAIL, f"[ADMIN] {subject}", email_html)
                
                await session.commit()
                print(f"[Background] Database updated for dataset {dataset_id}")
            else:
                print(f"[Background] Error: Dataset {dataset_id} not found in DB")
                
    except Exception as e:
        print(f"[Background] Critical error processing dataset {dataset_id}: {e}")
        # Try to update status to failed if possible
        try:
             from auth.database import async_session_maker
             async with async_session_maker() as session:
                stmt = select(Dataset).where(Dataset.id == dataset_id)
                db_result = await session.execute(stmt)
                dataset = db_result.scalar_one_or_none()
                if dataset:
                    dataset.processing_status = "failed"
                    await session.commit()
        except Exception:
            pass


@router.get("/", response_model=DatasetListResponse)
async def list_datasets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all datasets for the current user.
    """
    result = await db.execute(
        select(Dataset)
        .where(Dataset.user_id == current_user.id)
        .order_by(Dataset.created_at.desc())
    )
    datasets = result.scalars().all()
    
    return DatasetListResponse(
        datasets=[
            DatasetResponse(
                id=d.id,
                name=d.name,
                description=d.description,
                gcs_path=d.gcs_path,
                version=d.version,
                num_samples=d.num_samples,
                languages=d.languages,
                is_processed=d.is_processed,
                processing_status=d.processing_status,
                created_at=d.created_at.isoformat(),
            )
            for d in datasets
        ],
        total=len(datasets),
    )


@router.get("/{dataset_id}", response_model=DatasetStatsResponse)
async def get_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a specific dataset.
    """
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get split info from pipeline metadata (from GCS)
    pipeline = get_pipeline()
    info = pipeline.get_dataset_info(current_user.id, dataset_id) if pipeline else None
    split_stats = info.get("split_stats", {}) if info else {}
    
    return DatasetStatsResponse(
        dataset_id=dataset.id,
        name=dataset.name,
        total_samples=dataset.num_samples,
        train_samples=split_stats.get("train", {}).get("count", 0),
        val_samples=split_stats.get("val", {}).get("count", 0),
        test_samples=split_stats.get("test", {}).get("count", 0),
        languages=dataset.languages or {},
        processing_status=dataset.processing_status,
        created_at=dataset.created_at.isoformat(),
    )


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a dataset.
    """
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Delete from GCS
    pipeline = get_pipeline()
    if pipeline:
        pipeline.delete_dataset(current_user.id, dataset_id)
    
    # Delete from database
    await db.delete(dataset)
    await db.commit()
    
    return {"message": "Dataset deleted successfully"}


# =============================================================================
# Bias Detection Endpoints
# =============================================================================

class BiasMetricResponse(BaseModel):
    """Single bias dimension metrics."""
    dimension: str
    distribution: dict
    percentages: dict
    imbalance_score: float
    dominant_category: str
    minority_categories: List[str]
    recommendation: str
    severity: str


class BiasReportResponse(BaseModel):
    """Complete bias analysis report."""
    dataset_id: str
    total_samples: int
    analysis_timestamp: str
    overall_bias_score: float
    overall_severity: str
    recommendations: List[str]
    language_bias: Optional[BiasMetricResponse] = None
    complexity_bias: Optional[BiasMetricResponse] = None
    size_bias: Optional[BiasMetricResponse] = None
    documentation_bias: Optional[BiasMetricResponse] = None
    statistics: Optional[dict] = None


@router.get("/{dataset_id}/bias", response_model=BiasReportResponse)
async def get_bias_report(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get bias detection results for a dataset.
    
    Returns detailed analysis of potential biases in the dataset including:
    - **Language Distribution**: Imbalance across programming languages
    - **Code Complexity**: Distribution of simple vs complex code
    - **File Size**: Distribution of small vs large code samples
    - **Documentation**: Coverage of comments and docstrings
    
    Each dimension includes an imbalance score (0-1) and recommendations.
    """
    # Verify dataset exists and belongs to user
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get bias report from GCS
    pipeline = get_pipeline()
    bias_report = pipeline.get_bias_report(current_user.id, dataset_id) if pipeline else None
    
    if not bias_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bias report not found. Dataset may not have been fully processed."
        )
    
    # Convert to response format
    def convert_metric(metric_dict: Optional[dict]) -> Optional[BiasMetricResponse]:
        if not metric_dict:
            return None
        return BiasMetricResponse(**metric_dict)
    
    return BiasReportResponse(
        dataset_id=bias_report["dataset_id"],
        total_samples=bias_report["total_samples"],
        analysis_timestamp=bias_report["analysis_timestamp"],
        overall_bias_score=bias_report["overall_bias_score"],
        overall_severity=bias_report["overall_severity"],
        recommendations=bias_report.get("recommendations", []),
        language_bias=convert_metric(bias_report.get("language_bias")),
        complexity_bias=convert_metric(bias_report.get("complexity_bias")),
        size_bias=convert_metric(bias_report.get("size_bias")),
        documentation_bias=convert_metric(bias_report.get("documentation_bias")),
        statistics=bias_report.get("statistics"),
    )


@router.get("/{dataset_id}/bias/summary")
async def get_bias_summary(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a brief summary of bias detection results.
    
    Returns only the overall score, severity, and recommendations.
    """
    # Verify dataset exists
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get from pipeline metadata (GCS)
    pipeline = get_pipeline()
    info = pipeline.get_dataset_info(current_user.id, dataset_id) if pipeline else None
    
    if not info or "bias_summary" not in info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bias summary not available"
        )
    
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        **info["bias_summary"]
    }

