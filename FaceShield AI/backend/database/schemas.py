from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    email: str
    full_name: str

class TokenData(BaseModel):
    email: Optional[str] = None

class VerificationResponse(BaseModel):
    id: int
    user_id: int
    document_type: str
    ocr_data: Optional[Dict[str, Any]] = None
    match_score: float
    liveness_score: float
    fraud_risk_score: float
    status: str
    doc_photo_path: Optional[str] = None
    selfie_photo_path: Optional[str] = None
    processing_time: float
    created_at: datetime

    class Config:
        from_attributes = True

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
