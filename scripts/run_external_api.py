"""
Standalone server for external data API endpoints.
Run with: python scripts/run_external_api.py
"""

import sys
sys.path.insert(0, ".")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.external_data import router as external_data_router

# Create standalone FastAPI app
app = FastAPI(
    title="External Data API",
    description="API endpoints for external database data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include external data router
app.include_router(external_data_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "external-data-api"}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
    )
