from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.database import models, schemas
from backend.utils import auth_helper
import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    db_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email address already exists."
        )
        
    # Check if this is the first user; if so, make them an admin
    first_user = db.query(models.User).first()
    role = "admin" if first_user is None else "user"
    
    hashed_password = auth_helper.get_password_hash(user_in.password)
    new_user = models.User(
        email=user_in.email,
        password_hash=hashed_password,
        full_name=user_in.full_name,
        role=role,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Audit log
    audit_log = models.AuditLog(
        user_id=new_user.id,
        action=f"User signed up with role: {role}",
        ip_address="Local"
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"Registered user: {new_user.email} (ID: {new_user.id}, Role: {new_user.role})")
    return new_user

@router.post("/login", response_model=schemas.Token)
def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if not user or not auth_helper.verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User account is deactivated"
        )
        
    access_token_expires = datetime.timedelta(minutes=auth_helper.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_helper.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Audit log
    audit_log = models.AuditLog(
        user_id=user.id,
        action="User logged in successfully",
        ip_address="Local"
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"Logged in user: {user.email}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "email": user.email,
        "full_name": user.full_name
    }

@router.get("/profile", response_model=schemas.UserResponse)
def get_profile(current_user: models.User = Depends(auth_helper.get_current_user)):
    return current_user

@router.put("/profile", response_model=schemas.UserResponse)
def update_profile(
    user_update: schemas.UserBase,
    current_user: models.User = Depends(auth_helper.get_current_user),
    db: Session = Depends(get_db)
):
    # Check email uniqueness if email changed
    if user_update.email != current_user.email:
        email_check = db.query(models.User).filter(models.User.email == user_update.email).first()
        if email_check:
            raise HTTPException(status_code=400, detail="Email already in use.")
            
    current_user.full_name = user_update.full_name
    current_user.email = user_update.email
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/reset-password")
def reset_password(email: str, db: Session = Depends(get_db)):
    # Mock password reset
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email address not found")
        
    logger.info(f"Password reset link generated for email: {email}")
    # In production, send email reset link here.
    return {"message": "Password reset instructions have been sent to your email address."}

@router.post("/verify-email")
def verify_email(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email address not found")
        
    logger.info(f"Email verification email sent to: {email}")
    return {"message": "Verification link has been sent to your email address."}

# Admin only: List all users
@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(
    admin_user: models.User = Depends(auth_helper.get_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).all()
    return users
