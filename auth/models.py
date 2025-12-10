"""
Database Models for Multi-Tenant LLM Fine-Tuning Platform

This module defines SQLAlchemy ORM models for:
- Users (authentication and tenant identification)
- Datasets (user-uploaded code datasets)
- Adapters (trained LoRA adapters per user)
- TrainingJobs (fine-tuning job tracking)
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, 
    ForeignKey, Text, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
import enum
import uuid

Base = declarative_base()


def generate_uuid() -> str:
    """Generate a unique ID string."""
    return str(uuid.uuid4())


class JobStatus(enum.Enum):
    """Training job status enum."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class User(Base):
    """
    User model for multi-tenant authentication.
    Each user can have their own datasets and trained adapters.
    """
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Usage tracking
    total_training_hours: Mapped[float] = mapped_column(Float, default=0.0)
    total_tokens_generated: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    datasets: Mapped[List["Dataset"]] = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    adapters: Mapped[List["Adapter"]] = relationship("Adapter", back_populates="user", cascade="all, delete-orphan")
    training_jobs: Mapped[List["TrainingJob"]] = relationship("TrainingJob", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Dataset(Base):
    """
    Dataset model for user-uploaded code datasets.
    Each dataset is isolated to a specific user.
    """
    __tablename__ = "datasets"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Dataset metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Storage location
    gcs_path: Mapped[str] = mapped_column(String(500), nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)
    dvc_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Dataset statistics
    num_files: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    num_samples: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"python": 1000, "java": 500}
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="datasets")
    training_jobs: Mapped[List["TrainingJob"]] = relationship("TrainingJob", back_populates="dataset")
    
    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name={self.name}, user_id={self.user_id})>"


class Adapter(Base):
    """
    Adapter model for trained LoRA adapters.
    Each adapter belongs to a specific user and is trained on their dataset.
    """
    __tablename__ = "adapters"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    training_job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("training_jobs.id"), nullable=True)
    
    # Adapter metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Model information
    base_model: Mapped[str] = mapped_column(String(255), default="bigcode/starcoder2-3b")
    
    # Storage location
    gcs_path: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Training metrics
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"train_loss": 0.5, "eval_loss": 0.6, "codebleu": 0.75}
    
    # LoRA configuration used
    lora_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Deployment status
    is_deployed: Mapped[bool] = mapped_column(Boolean, default=False)
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Usage statistics
    inference_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_generated: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="adapters")
    training_job: Mapped[Optional["TrainingJob"]] = relationship("TrainingJob", back_populates="adapter")
    
    def __repr__(self) -> str:
        return f"<Adapter(id={self.id}, name={self.name}, user_id={self.user_id})>"


class TrainingJob(Base):
    """
    Training job model for tracking fine-tuning runs.
    """
    __tablename__ = "training_jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    
    # Job metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Status tracking
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    
    # Configuration
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Stores full training configuration: lora params, learning rate, etc.
    
    # Training metrics (updated during training)
    current_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    final_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Compute usage
    gpu_hours: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    
    # MLflow integration
    mlflow_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="training_jobs")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="training_jobs")
    adapter: Mapped[Optional["Adapter"]] = relationship("Adapter", back_populates="training_job", uselist=False)
    
    def __repr__(self) -> str:
        return f"<TrainingJob(id={self.id}, status={self.status}, user_id={self.user_id})>"


class FeedbackLog(Base):
    """
    Feedback log for tracking user ratings on model outputs.
    Used for continuous improvement and retraining decisions.
    """
    __tablename__ = "feedback_logs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    adapter_id: Mapped[str] = mapped_column(String(36), ForeignKey("adapters.id"), nullable=False)
    
    # Request/Response info (anonymized)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Hash of prompt for privacy
    response_length: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Feedback
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 or thumbs up/down (1/0)
    feedback_type: Mapped[str] = mapped_column(String(50), default="thumbs")  # "thumbs" or "stars"
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<FeedbackLog(id={self.id}, rating={self.rating}, adapter_id={self.adapter_id})>"
