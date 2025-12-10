"""
FastAPI Dependencies for Authentication

Provides dependency injection for auth and tenant context.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from auth.database import get_db
from auth.models import User
from auth.jwt_handler import verify_token, TokenData

# Security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Extracts user from JWT token and validates against database.
    
    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current user and verify they are active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get current user (for public endpoints).
    
    Returns None if no valid token provided.
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    if payload is None:
        return None
    
    user_id: str = payload.get("sub")
    if user_id is None:
        return None
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    return user


class TenantContext:
    """
    Context class for multi-tenant operations.
    
    Provides tenant-specific paths and validation.
    """
    
    def __init__(self, user: User):
        self.user = user
        self.user_id = user.id
        self.email = user.email
    
    @property
    def datasets_prefix(self) -> str:
        """GCS prefix for user's datasets."""
        return f"users/{self.user_id}/datasets"
    
    @property
    def adapters_prefix(self) -> str:
        """GCS prefix for user's adapters."""
        return f"users/{self.user_id}/adapters"
    
    @property
    def local_data_path(self) -> str:
        """Local path for user's data (development)."""
        return f"./data/users/{self.user_id}"


async def get_tenant_context(
    current_user: User = Depends(get_current_user)
) -> TenantContext:
    """
    Dependency to get tenant context for the current user.
    
    Use this in endpoints that need tenant-specific operations.
    """
    return TenantContext(current_user)
