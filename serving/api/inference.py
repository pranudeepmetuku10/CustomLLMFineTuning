from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from auth.database import get_db
from auth.dependencies import get_current_user
from auth.models import User, TrainingJob, JobStatus
from serving.engine import InferenceEngine

router = APIRouter(prefix="/models", tags=["Inference"])
engine = InferenceEngine()

class PredictRequest(BaseModel):
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.2

class PredictResponse(BaseModel):
    generated_text: str
    model_id: str

@router.post("/{model_id}/predict", response_model=PredictResponse)
async def predict(
    model_id: str,
    request: PredictRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate text using a fine-tuned model.
    Downloads the adapter if not already cached.
    """
    # 1. Verify Model Ownership & Status
    stmt = select(TrainingJob).where(TrainingJob.id == model_id, TrainingJob.user_id == current_user.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Model not found")
        
    if job.status not in [JobStatus.COMPLETED, JobStatus.SUCCEEDED]:
        raise HTTPException(status_code=400, detail=f"Model is not ready (Status: {job.status})")
        
    # 2. Get Adapter Path
    # The output_dir in config usually points to the model directory on GCS
    # e.g. gs://bucket/users/.../models/.../run-id
    # We need to ensure we have the correct path to the adapter files
    # Usually the adapter is stored AT that path.
    
    # Let's extract from a known field or reconstruct
    # job.config["output_dir"] seems reliable from train.py
    gcs_path = job.config.get("output_dir")
    
    # Fallback if config is missing (legacy)
    if not gcs_path:
        raise HTTPException(status_code=500, detail="Model configuration missing output path")
        
    # 3. Load Adapter & Generate
    try:
        # This will download if needed and hot-swap
        engine.load_adapter(model_id, gcs_path)
        
        result = engine.generate(
            request.prompt, 
            max_new_tokens=request.max_tokens, 
            temperature=request.temperature
        )
        
        return PredictResponse(
            generated_text=result,
            model_id=model_id
        )
        
    except Exception as e:
        print(f"Inference Error: {e}")
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
