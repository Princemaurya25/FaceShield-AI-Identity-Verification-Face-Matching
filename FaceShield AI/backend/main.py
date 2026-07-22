from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from backend.config import settings
from backend.database.db import engine, Base
from backend.api import auth, verification, analytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create database tables at startup
try:
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
except Exception as e:
    logger.critical(f"Database initialization failed: {e}")

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FaceShield AI - Full-stack Identity Verification & Face Matching API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to React domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files for Uploads and Reports
# This enables the frontend to fetch and display uploaded cards, selfies, and PDF reports directly
try:
    app.mount("/uploads/documents", StaticFiles(directory=str(settings.DOCUMENTS_DIR)), name="documents")
    app.mount("/uploads/selfies", StaticFiles(directory=str(settings.SELFIES_DIR)), name="selfies")
    app.mount("/uploads/reports", StaticFiles(directory=str(settings.REPORTS_DIR)), name="reports")
    logger.info("Static file mounts configured.")
except Exception as e:
    logger.error(f"Error configuring static file mounts: {e}")

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(verification.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
def read_root():
    return {
        "status": "online",
        "app_name": settings.PROJECT_NAME,
        "api_version": "v1.0.0",
        "documentation_url": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
