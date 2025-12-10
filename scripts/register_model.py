
import asyncio
import os
import sys
import uuid
import shutil
from typing import Optional
import argparse
from datetime import datetime

# Add parent dir to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from dotenv import load_dotenv

from auth.database import async_session_maker
from auth.models import User, TrainingJob, Dataset, JobStatus

# Load env vars
load_dotenv()

async def register_model(local_path: str, model_name: str, email: str):
    """
    1. Uploads local model files to GCS.
    2. Inserts a SUCCEEDED job record into the DB.
    """
    
    # 0. Login / Get User
    print(f"Finding user {email}...")
    async with async_session_maker() as db:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"User {email} not found! Please register first via API.")
            return

        # 1. Prepare GCS Path
        job_id = str(uuid.uuid4())
        bucket_name = os.getenv("GCS_ADAPTERS_BUCKET")
        if not bucket_name:
            print("Error: GCS_ADAPTERS_BUCKET not set in .env")
            return
            
        gcs_destination = f"gs://{bucket_name}/users/{user.id}/models/{job_id}"
        print(f"Target GCS Path: {gcs_destination}")
        
        # 2. Upload Files
        print(f"Uploading files from {local_path}...")
        try:
            from google.cloud import storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            
            # Destination prefix (remove gs://bucket/)
            prefix = f"users/{user.id}/models/{job_id}"
            
            file_count = 0
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_file_path, local_path)
                    blob_path = f"{prefix}/{relative_path}"
                    
                    blob = bucket.blob(blob_path)
                    blob.upload_from_filename(local_file_path)
                    print(f"Uploaded: {relative_path}")
                    file_count += 1
            
            if file_count == 0:
                print("No files found in directory!")
                return
                
        except Exception as e:
            print(f"Upload failed: {e}")
            return

        # 3. Create Dummy Dataset (if needed) or use existing one?
        # For simplicity, we'll try to find ANY processed dataset or create a placeholder
        stmt = select(Dataset).where(Dataset.user_id == user.id, Dataset.is_processed == True)
        result = await db.execute(stmt)
        dataset = result.scalars().first()
        
        if not dataset:
            print("No processed dataset found for user. Cannot link job.")
            # Create dummy?
            dataset = Dataset(
                id=str(uuid.uuid4()),
                user_id=user.id,
                name="manual-upload-placeholder",
                gcs_path="gs://placeholder",
                is_processed=True
            )
            db.add(dataset)
            await db.commit()
            print("Created placeholder dataset.")

        # 4. Insert Job Record
        print("Registering job in database...")
        job = TrainingJob(
            id=job_id,
            user_id=user.id,
            dataset_id=dataset.id,
            name=model_name,
            status=JobStatus.COMPLETED, # Mark as DONE
            created_at=datetime.utcnow(),
            config={
                "model_name": "bigcode/starcoder2-3b",
                "output_dir": gcs_destination, # Crucial for inference
                "run_name": "manual-upload"
            }
        )
        db.add(job)
        await db.commit()
        
        print("\nSUCCESS!")
        print(f"Model '{model_name}' (ID: {job_id}) registered.")
        print("You can now run 'python scripts/test_inference_flow.py' to use it.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload and register a local model")
    parser.add_argument("--path", required=True, help="Local path to model directory (containing adapter_config.json)")
    parser.add_argument("--name", default="My Local Model", help="Display name for the model")
    parser.add_argument("--email", default="user@example.com", help="User email to owner")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"Path does not exist: {args.path}")
        sys.exit(1)
        
    asyncio.run(register_model(args.path, args.name, args.email))
