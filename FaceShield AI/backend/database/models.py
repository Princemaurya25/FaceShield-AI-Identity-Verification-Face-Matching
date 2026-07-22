import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from backend.database.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="user") # 'user' or 'admin'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    verifications = relationship("VerificationRecord", back_populates="user")

class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(String, nullable=False) # 'Aadhaar', 'PAN', 'Passport', 'Driving License', 'Voter ID'
    ocr_data = Column(JSON, nullable=True) # Extracted OCR text fields
    
    # AI Scores
    match_score = Column(Float, default=0.0)
    liveness_score = Column(Float, default=0.0)
    fraud_risk_score = Column(Float, default=0.0)
    status = Column(String, default="pending") # 'success', 'failed', 'flagged'
    
    # File Paths
    doc_photo_path = Column(String, nullable=True)
    selfie_photo_path = Column(String, nullable=True)
    
    processing_time = Column(Float, default=0.0) # In seconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="verifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
