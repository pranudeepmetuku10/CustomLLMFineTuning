"""
LLM Fine-Tuning Platform - Main FastAPI Application

Multi-tenant platform for fine-tuning LLMs using QLoRA.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from auth.routes import router as auth_router
from data.routes import router as data_router
from training.routes import router as training_router
from serving.api.inference import router as inference_router
from auth.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    print("Starting LLM Fine-Tuning Platform...")
    
    # Initialize database tables
    try:
        await init_db()
        print("Database initialized")
    except Exception as e:
        print(f"Database initialization warning: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down LLM Fine-Tuning Platform...")


# Create FastAPI app
app = FastAPI(
    title="LLM Fine-Tuning Platform",
    description="""
    Multi-tenant platform for fine-tuning large language models using QLoRA.
    
    ## Features
    - User authentication with JWT
    - Per-user dataset management
    - QLoRA fine-tuning with StarCoder2-3B
    - Dynamic adapter loading for inference
    - Usage tracking and monitoring
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(training_router, prefix="/api")
app.include_router(inference_router, prefix="/api")


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API info."""
    return {
        "name": "LLM Fine-Tuning Platform",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy"}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness check - verifies database connection."""
    from sqlalchemy import text
    from auth.database import engine
    
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "database": db_status
    }


# =============================================================================
# Run with: uvicorn serving.api.main:app --reload
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "serving.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
