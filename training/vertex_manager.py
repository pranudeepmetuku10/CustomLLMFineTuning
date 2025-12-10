import os
from google.cloud import aiplatform
from typing import Optional, List, Dict
import pandas as pd
import google.auth

class VertexManager:
    def __init__(self, project_id: str, location: str = "us-central1", staging_bucket: str = None):
        self.project_id = project_id
        self.location = location
        self.staging_bucket = staging_bucket
        
        aiplatform.init(
            project=project_id,
            location=location,
            staging_bucket=staging_bucket
        )

    def submit_training_job(
        self,
        user_id: str,
        dataset_id: str,
        dataset_uri: str,
        image_uri: str,
        job_id: str,
        model_name: str = "starcoder2-3b",
        epochs: int = 3,
        batch_size: int = 4,
        experiment_name: str = "llm-finetuning",
        run_name: Optional[str] = None,
        checkpoint_path: Optional[str] = None,
        user_email: Optional[str] = None,
        service_account: Optional[str] = None
    ) -> aiplatform.CustomContainerTrainingJob:
        """
        Submit a Custom Container Training Job to Vertex AI
        """
        
        job_name = f"finetune-{user_id[:8]}-{dataset_id[:8]}-{job_id[:6]}"
        
        # Unique output directory for this job
        adapters_bucket = os.getenv("GCS_ADAPTERS_BUCKET")
        output_dir = f"gs://{adapters_bucket}/users/{user_id}/models/{job_id}"
        
        # Define the job
        # Pass SMTP environment variables to the container
        env_vars = {
            "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
            "SMTP_USER": os.getenv("SMTP_USER", ""),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", "")
        }
        
        job = aiplatform.CustomContainerTrainingJob(
            display_name=job_name,
            container_uri=image_uri,
        )
        
        cmds = [
            f"--model_name={model_name}",
            f"--dataset_path={dataset_uri}",
            f"--output_dir={output_dir}",
            f"--epochs={str(epochs)}",
            f"--batch_size={str(batch_size)}",
            f"--project_id={self.project_id}",
            f"--location={self.location}",
            f"--experiment_name={experiment_name}"
        ]
        
        if run_name:
            cmds.append(f"--run_name={run_name}")
            
        if checkpoint_path:
            cmds.append(f"--resume_from_checkpoint={checkpoint_path}")
            
        if user_email:
            cmds.append(f"--user_email={user_email}")
        
        # Determine accelerator config from env
        accelerator_type = os.getenv("TRAINING_ACCELERATOR_TYPE", "NVIDIA_L4")
        if accelerator_type == "NVIDIA_TESLA_T4":
            machine_type = "n1-standard-4"
        elif accelerator_type == "NVIDIA_L4":
            machine_type = "g2-standard-4" # L4 machine type
        elif accelerator_type == "NVIDIA_TESLA_V100":
            machine_type = "n1-standard-8"
        elif accelerator_type == "NVIDIA_TESLA_A100":
             machine_type = "a2-highgpu-1g"
        else:
            # Fallback to T4 default if unknown
            accelerator_type = "NVIDIA_TESLA_T4"
            machine_type = "n1-standard-4"

        print(f"Submitting job with {accelerator_type} on {machine_type}")

        # Submit the job
        model = job.run(
            args=cmds,
            environment_variables=env_vars,
            replica_count=1,
            machine_type=machine_type, 
            accelerator_type=accelerator_type,
            accelerator_count=1,
            sync=False,
            service_account=service_account
        )
        
        return job

    def get_experiment_runs(self, experiment_name: str = "llm-finetuning") -> List[Dict]:
        """
        Get all runs and metrics from an experiment.
        Returns deserialized list of dicts.
        """
        try:
            df = aiplatform.get_experiment_df(experiment_name)
            # Filter and clean
            if df.empty:
                return []
                
            # Convert to list of dicts
            # df columns look like: 'metric.perplexity', 'param.learning_rate', 'run_name'
            results = []
            for _, row in df.iterrows():
                run_data = {"run_name": row.name} # Index is run_name usually? Or 'run_name' col
                # Robust extraction
                for col in df.columns:
                    if col == "run_name":
                        run_data["run_name"] = row[col]
                    elif col.startswith("metric."):
                        run_data[col.replace("metric.", "")] = row[col]
                    elif col.startswith("param."):
                        run_data[col.replace("param.", "")] = row[col]
                        
                results.append(run_data)
            return results
        except Exception as e:
            print(f"Error fetching experiment runs: {e}")
            return []

    def get_job_status(self, job_id: str) -> str:
        """
        Get the status of a specific training job by ID (Training Pipeline ID).
        """
        try:
            # Rehydrate the job
            # Note: job_id here refers to the resource name or ID string
            job_resource_name = f"projects/{self.project_id}/locations/{self.location}/trainingPipelines/{job_id}"
            job = aiplatform.CustomContainerTrainingJob.get(resource_name=job_resource_name)
            
            # Map Vertex State to our Enum
            # JobState: JOB_STATE_UNSPECIFIED, QUEUED, PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLING, CANCELLED, PAUSED
            state = job.state
            
            # Convert to string (e.g. JobState.SUCCEEDED -> "SUCCEEDED")
            return state.name
        except Exception as e:
            print(f"Error checking status for job {job_id}: {e}")
            return "UNKNOWN"

    def check_gcs_file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS.
        """
        try:
            if not gcs_path.startswith("gs://"):
                return False
                
            from google.cloud import storage
            client = storage.Client(project=self.project_id)
            
            # Parse gs://bucket/path/to/file
            path_parts = gcs_path.replace("gs://", "").split("/")
            bucket_name = path_parts[0]
            blob_name = "/".join(path_parts[1:])
            
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            print(f"Error checking GCS file {gcs_path}: {e}")
            return False
