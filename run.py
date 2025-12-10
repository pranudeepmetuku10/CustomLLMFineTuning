"""
Quick run script for the API server.

Usage: python run.py
"""

import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    debug = os.getenv("DEBUG", "true").lower() == "true"
    
    uvicorn.run(
        "serving.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=debug,
        log_level="info" if not debug else "debug"
    )
