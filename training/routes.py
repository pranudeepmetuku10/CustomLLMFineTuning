from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from auth.database import get_db
from auth.dependencies import get_current_user
from auth.models import User, TrainingJob, Dataset, JobStatus
from training.vertex_manager import VertexManager
import os
import uuid
from typing import Optional

router = APIRouter(prefix="/models", tags=["Training"])

class TrainRequest(BaseModel):
    dataset_id: str
    model_name: str = "bigcode/starcoder2-3b"
    epochs: int = 3
    batch_size: int = 4
    parent_job_id: Optional[str] = None

@router.post("/train")
async def trigger_training(
    request: TrainRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger a fine-tuning job on Vertex AI.
    """
    
    # 1. Verify Dataset
    stmt = select(Dataset).where(Dataset.id == request.dataset_id, Dataset.user_id == current_user.id)
    result = await db.execute(stmt)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    if not dataset.is_processed:
         raise HTTPException(status_code=400, detail="Dataset must be processed before training")

    # 2. Infrastructure Config
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCS_PROJECT")
    location = os.getenv("GCP_LOCATION", "us-central1")
    bucket_name = os.getenv("GCS_BUCKET") or os.getenv("GCS_DATASETS_BUCKET") # Main bucket
    staging_bucket = f"gs://{bucket_name}"
    image_uri = os.getenv("TRAINING_IMAGE_URI")
    
    if not project_id or not bucket_name or not image_uri:
        raise HTTPException(
            status_code=500, 
            detail="Training infrastructure not configured (Missing GCP_PROJECT_ID, GCS_BUCKET, or TRAINING_IMAGE_URI)"
        )
        
    # 3. Check Parent Job (Retraining)
    checkpoint_path = None
    if request.parent_job_id:
        stmt = select(TrainingJob).where(TrainingJob.id == request.parent_job_id, TrainingJob.user_id == current_user.id)
        result = await db.execute(stmt)
        parent_job = result.scalar_one_or_none()
        
        if not parent_job:
            raise HTTPException(status_code=404, detail="Parent job not found for retraining")
        
        # Construct path (legacy jobs might point to general path, new jobs point to precise path)
        # We assume new path structure: users/{uid}/models/{did}/{jid}
        # But wait, parent job might have used old logic!
        # If parent_job status is COMPLETED, we assume it's in the standard path.
        # For simplicity, we enforce new structure going forward. 
        # Checkpoint path:
        checkpoint_path = f"{staging_bucket}/users/{parent_job.user_id}/models/{parent_job.dataset_id}/{parent_job.id}"

    # 4. Create Job Record
    job_id = str(uuid.uuid4())
    run_name = f"run-{job_id[:8]}"
    
    job = TrainingJob(
        id=job_id,
        user_id=current_user.id,
        dataset_id=dataset.id,
        name=f"finetune-{dataset.name}-{job_id[:6]}",
        status=JobStatus.PENDING,
        config={
            "model_name": request.model_name,
            "epochs": request.epochs,
            "batch_size": request.batch_size,
            "run_name": run_name,
            "parent_job_id": request.parent_job_id
        }
    )
    db.add(job)
    await db.commit()
    
    # 5. Submit to Vertex AI
    try:
        manager = VertexManager(
            project_id=project_id,
            location=location,
            staging_bucket=staging_bucket
        )
        
        # Determine paths
        dataset_uri = dataset.gcs_path 
        if not dataset_uri.startswith("gs://"):
            dataset_uri = f"gs://{bucket_name}/{dataset_uri}"

        # Submit
        vertex_job = manager.submit_training_job(
            user_id=current_user.id,
            dataset_id=dataset.id,
            dataset_uri=dataset_uri,
            image_uri=image_uri,
            job_id=job_id,
            model_name=request.model_name,
            epochs=request.epochs,
            batch_size=request.batch_size,
            run_name=run_name,
            checkpoint_path=checkpoint_path,
            user_email=current_user.email,
            service_account=os.getenv("VERTEX_SERVICE_ACCOUNT")
        )
        
        # Update job status
        job.status = JobStatus.QUEUED
        await db.commit()
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Training job submitted successfully",
            "run_name": run_name
        }
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to submit training job: {str(e)}")

@router.get("/")
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all training jobs/models with their metrics.
    """
    # 1. Fetch Jobs from DB
    stmt = select(TrainingJob).where(TrainingJob.user_id == current_user.id).order_by(TrainingJob.created_at.desc())
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    
    # 2. Fetch Vertex Experiment Metrics
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    metrics_map = {}
    
    if project_id:
        try:
            manager = VertexManager(project_id=project_id)
            runs = manager.get_experiment_runs()
            # Create map by run_name
            for run in runs:
                if "run_name" in run:
                    metrics_map[run["run_name"]] = run
        except Exception as e:
            print(f"Warning: Failed to fetch experiment metrics: {e}")
            
    # 2.5 Sync Job Status (Check GCS for completion)
    for job in jobs:
        if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            try:
                # Check if the output directory has the model files
                output_dir = job.config.get("output_dir")
                if output_dir:
                    # Look for adapter_config.json which confirms Peft save success
                    check_path = f"{output_dir}/adapter_config.json"
                    print(f"Checking GCS for Job {job.id}: {check_path}")
                    
                    # We need a manager instance to check GCS
                    if not 'manager' in locals():
                         manager = VertexManager(project_id=project_id)
                         
                    exists = manager.check_gcs_file_exists(check_path)
                    print(f"File exists? {exists}")
                    
                    if exists:
                         print(f"Marking Job {job.id} as COMPLETED")
                         job.status = JobStatus.COMPLETED
                         await db.commit()
            except Exception:
                pass
    
    # 3. Merge
    response = []
    for job in jobs:
        job_data = {
            "id": job.id,
            "name": job.name,
            "status": job.status,
            "created_at": job.created_at,
            "dataset_id": job.dataset_id,
            "config": job.config,
            "metrics": job.final_metrics or {}
        }
        
        # Try to find extra metrics from Vertex
        run_name = job.config.get("run_name")
        if run_name and run_name in metrics_map:
            # Update metrics with Vertex data (perplexity, eval_loss, etc.)
            vertex_metrics = metrics_map[run_name]
            # Exclude params, keep metrics
            stats = {k: v for k, v in vertex_metrics.items() if k not in ["run_name", "state"]}
            job_data["metrics"].update(stats)
            
        response.append(job_data)
        
    return response
