import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "FaceShield AI"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkeyforfaceshieldaiidentitymatching2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./faceshield.db")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Uploads
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    DOCUMENTS_DIR: Path = UPLOAD_DIR / "documents"
    SELFIES_DIR: Path = UPLOAD_DIR / "selfies"
    REPORTS_DIR: Path = UPLOAD_DIR / "reports"
    
    # Verification Thresholds
    FACE_MATCH_THRESHOLD: float = 0.60  # Cosine similarity threshold for InceptionResnetV1
    LIVENESS_THRESHOLD: float = 0.50     # Spoofing check threshold
    QUALITY_THRESHOLD: float = 0.40      # Quality check score
    
    class Config:
        case_sensitive = True

settings = Settings()

# Ensure directories exist
settings.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
settings.SELFIES_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
