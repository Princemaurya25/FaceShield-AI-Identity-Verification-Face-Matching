from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime
from backend.database.db import get_db
from backend.database import models
from backend.utils import auth_helper

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/summary")
def get_analytics_summary(
    current_user: models.User = Depends(auth_helper.get_current_user),
    db: Session = Depends(get_db)
):
    # Retrieve verifications base query
    verify_query = db.query(models.VerificationRecord)
    
    # If user is not admin, scope to their own verifications
    is_admin = current_user.role == "admin"
    if not is_admin:
        verify_query = verify_query.filter(models.VerificationRecord.user_id == current_user.id)
        
    total_verifications = verify_query.count()
    success_verifications = verify_query.filter(models.VerificationRecord.status == "success").count()
    failed_verifications = verify_query.filter(models.VerificationRecord.status == "failed").count()
    flagged_verifications = verify_query.filter(models.VerificationRecord.status == "flagged").count()
    
    # Fraud alerts count (where fraud risk score >= 0.50)
    fraud_attempts = verify_query.filter(models.VerificationRecord.fraud_risk_score >= 0.50).count()
    
    success_rate = (success_verifications / total_verifications * 100) if total_verifications > 0 else 0.0
    
    # 1. Document distribution
    doc_distribution = []
    doc_counts = (
        db.query(models.VerificationRecord.document_type, func.count(models.VerificationRecord.id))
        .filter(models.VerificationRecord.user_id == current_user.id if not is_admin else True)
        .group_by(models.VerificationRecord.document_type)
        .all()
    )
    for doc_type, count in doc_counts:
        doc_distribution.append({"name": doc_type, "value": count})
        
    # 2. Timeline data (last 7 days)
    timeline_data = []
    today = datetime.datetime.utcnow().date()
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min)
        day_end = datetime.datetime.combine(day, datetime.time.max)
        
        day_total = (
            verify_query.filter(models.VerificationRecord.created_at.between(day_start, day_end))
            .count()
        )
        day_success = (
            verify_query.filter(
                models.VerificationRecord.created_at.between(day_start, day_end),
                models.VerificationRecord.status == "success"
            )
            .count()
        )
        day_fraud = (
            verify_query.filter(
                models.VerificationRecord.created_at.between(day_start, day_end),
                models.VerificationRecord.fraud_risk_score >= 0.50
            )
            .count()
        )
        
        timeline_data.append({
            "date": day.strftime("%b %d"),
            "verifications": day_total,
            "success": day_success,
            "frauds": day_fraud
        })
        
    # 3. Audit logs (Only available to Admin)
    audit_logs = []
    if is_admin:
        logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(10).all()
        for l in logs:
            user_email = "System/Unknown"
            if l.user_id:
                user = db.query(models.User).filter(models.User.id == l.user_id).first()
                if user:
                    user_email = user.email
            
            audit_logs.append({
                "id": l.id,
                "user_email": user_email,
                "action": l.action,
                "ip_address": l.ip_address,
                "timestamp": l.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })
            
    # Total Users count (Only for Admin)
    total_users = db.query(models.User).count() if is_admin else 1
    
    return {
        "total_users": total_users,
        "total_verifications": total_verifications,
        "success_verifications": success_verifications,
        "failed_verifications": failed_verifications,
        "flagged_verifications": flagged_verifications,
        "success_rate": round(success_rate, 2),
        "fraud_attempts": fraud_attempts,
        "document_distribution": doc_distribution,
        "timeline_data": timeline_data,
        "audit_logs": audit_logs
    }
