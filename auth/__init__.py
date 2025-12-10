"""
Auth module for multi-tenant LLM platform.
"""

from auth.models import User, Dataset, Adapter, TrainingJob, FeedbackLog, JobStatus, Base
from auth.database import get_db, init_db, engine
from auth.jwt_handler import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    verify_token, get_user_id_from_token
)
from auth.dependencies import get_current_user, get_tenant_context, TenantContext
from auth.routes import router as auth_router

__all__ = [
    # Models
    "User",
    "Dataset", 
    "Adapter",
    "TrainingJob",
    "FeedbackLog",
    "JobStatus",
    "Base",
    # Database
    "get_db",
    "init_db",
    "engine",
    # JWT
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_user_id_from_token",
    # Dependencies
    "get_current_user",
    "get_tenant_context",
    "TenantContext",
    # Router
    "auth_router",
]
