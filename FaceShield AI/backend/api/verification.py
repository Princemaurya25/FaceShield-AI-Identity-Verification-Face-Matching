from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
import time
import os
import shutil
import uuid
import cv2
import numpy as np
import logging
from backend.database.db import get_db
from backend.database import models, schemas
from backend.utils import auth_helper
from backend.config import settings
from backend.ai_models.ai_engine import ai_engine
from backend.ai_models.liveness import check_liveness
from backend.ai_models.ocr_engine import ocr_engine
from backend.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["Identity Verification"])

@router.post("/verify", response_model=schemas.VerificationResponse)
def verify_identity(
    document: UploadFile = File(...),
    selfie: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: models.User = Depends(auth_helper.get_current_user),
    db: Session = Depends(get_db)
):
    start_time = time.time()
    
    # 1. Validate document type
    valid_types = ["Aadhaar", "PAN", "Passport", "Driving License", "Voter ID"]
    if document_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Must be one of: {', '.join(valid_types)}"
        )
        
    # 2. Secure file uploads and save them
    doc_filename = f"doc_{uuid.uuid4()}_{document.filename}"
    selfie_filename = f"selfie_{uuid.uuid4()}_{selfie.filename}"
    
    doc_path = settings.DOCUMENTS_DIR / doc_filename
    selfie_path = settings.SELFIES_DIR / selfie_filename
    
    try:
        with doc_path.open("wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
        with selfie_path.open("wb") as buffer:
            shutil.copyfileobj(selfie.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write uploaded files: {e}")
        raise HTTPException(status_code=500, detail="Failed to store uploaded files.")
        
    try:
        # 3. Read saved images with OpenCV
        doc_img = cv2.imread(str(doc_path))
        selfie_img = cv2.imread(str(selfie_path))
        
        if doc_img is None or selfie_img is None:
            raise ValueError("Invalid image file format.")
            
        # 4. Perform face detection and alignment
        doc_box, doc_landmarks = ai_engine.detect_face(doc_img)
        selfie_box, selfie_landmarks = ai_engine.detect_face(selfie_img)
        
        if doc_box is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No face detected in the identity document. Please ensure the card photo is clear and visible."
            )
            
        if selfie_box is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No face detected in the live selfie. Please align your face inside the camera view."
            )
            
        # Align and crop faces
        doc_face = ai_engine.align_and_crop_face(doc_img, doc_box, doc_landmarks)
        selfie_face = ai_engine.align_and_crop_face(selfie_img, selfie_box, selfie_landmarks)
        
        # 5. Assess selfie quality
        selfie_quality = ai_engine.assess_face_quality(selfie_img)
        if selfie_quality["is_blurry"]:
            logger.warning("Selfie quality is blurry.")
            
        # 6. Face Embedding & Similarity Matching
        doc_embedding = ai_engine.get_face_embedding(doc_face)
        selfie_embedding = ai_engine.get_face_embedding(selfie_face)
        
        if doc_embedding is None or selfie_embedding is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate face biometric embeddings."
            )
            
        match_score, is_match = ai_engine.calculate_similarity(doc_embedding, selfie_embedding)
        
        # 7. Liveness & Anti-spoofing Check on Selfie
        liveness_score, liveness_details = check_liveness(selfie_img)
        is_live = liveness_score >= settings.LIVENESS_THRESHOLD
        
        # 8. Extract OCR fields from document
        ocr_result = ocr_engine.parse_document(doc_img, document_type)
        
        # 9. Fraud risk assessment
        # High risk if mismatch, spoofing detected, or bad quality combination
        fraud_risk = 0.0
        if not is_match:
            fraud_risk += 0.50
        if not is_live:
            fraud_risk += 0.40
        if selfie_quality["is_blurry"]:
            fraud_risk += 0.10
        fraud_risk = min(1.0, fraud_risk)
        
        # Determine status
        if is_match and is_live:
            status_val = "success"
        elif not is_live:
            status_val = "failed"  # Failed due to spoofing / liveness
        else:
            status_val = "flagged"  # Flagged due to profile mismatch or quality issues
            
        processing_time = time.time() - start_time
        
        # 10. Store record in DB
        new_record = models.VerificationRecord(
            user_id=current_user.id,
            document_type=document_type,
            ocr_data=ocr_result,
            match_score=match_score,
            liveness_score=liveness_score,
            fraud_risk_score=fraud_risk,
            status=status_val,
            doc_photo_path=os.path.basename(str(doc_path)),
            selfie_photo_path=os.path.basename(str(selfie_path)),
            processing_time=processing_time
        )
        
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        
        # Audit Log
        audit = models.AuditLog(
            user_id=current_user.id,
            action=f"Verified identity document {document_type} (Record ID: {new_record.id}). Result: {status_val}",
            ip_address="Local"
        )
        db.add(audit)
        db.commit()
        
        logger.info(f"Verification complete (ID: {new_record.id}) - Match Score: {match_score:.2f}%, Liveness: {liveness_score:.2f}, Status: {status_val}")
        return new_record
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in verification pipeline: {e}")
        # Clean up files if failed
        if doc_path.exists():
            doc_path.unlink()
        if selfie_path.exists():
            selfie_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Verification pipeline failed: {str(e)}"
        )

@router.get("/history", response_model=list[schemas.VerificationResponse])
def get_verification_history(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    document_type: str = None,
    current_user: models.User = Depends(auth_helper.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.VerificationRecord)
    
    # Non-admin users can only view their own history
    if current_user.role != "admin":
        query = query.filter(models.VerificationRecord.user_id == current_user.id)
        
    if status:
        query = query.filter(models.VerificationRecord.status == status)
        
    if document_type:
        query = query.filter(models.VerificationRecord.document_type == document_type)
        
    # Sort newest first
    records = query.order_by(models.VerificationRecord.created_at.desc()).offset(skip).limit(limit).all()
    return records

@router.get("/report/{record_id}/pdf")
def download_pdf_report(
    record_id: int,
    current_user: models.User = Depends(auth_helper.get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(models.VerificationRecord).filter(models.VerificationRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Verification record not found.")
        
    # Restrict users from accessing others' reports
    if current_user.role != "admin" and record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
        
    # Get user profile fullname
    record_user = db.query(models.User).filter(models.User.id == record.user_id).first()
    fullname = record_user.full_name if record_user else "Unknown User"
    
    try:
        # Generate PDF
        pdf_path = ReportService.generate_pdf_report(record, fullname)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"FaceShield_Verification_Report_{record.id}.pdf"
        )
    except Exception as e:
        logger.error(f"Failed to generate report PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to compile PDF report.")

@router.get("/report/export/csv")
def download_csv_history(
    current_user: models.User = Depends(auth_helper.get_current_user),
    db: Session = Depends(get_db)
):
    # Retrieve records
    query = db.query(models.VerificationRecord)
    if current_user.role != "admin":
        query = query.filter(models.VerificationRecord.user_id == current_user.id)
        
    records = query.order_by(models.VerificationRecord.created_at.desc()).all()
    csv_data = ReportService.generate_csv(records)
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=faceshield_verifications_export.csv"}
    )

@router.delete("/history/{record_id}", status_code=status.HTTP_200_OK)
def delete_history_record(
    record_id: int,
    admin_user: models.User = Depends(auth_helper.get_admin_user),
    db: Session = Depends(get_db)
):
    record = db.query(models.VerificationRecord).filter(models.VerificationRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
        
    # Delete uploaded images from disk
    doc_img_path = settings.DOCUMENTS_DIR / record.doc_photo_path if record.doc_photo_path else None
    selfie_img_path = settings.SELFIES_DIR / record.selfie_photo_path if record.selfie_photo_path else None
    
    try:
        if doc_img_path and doc_img_path.exists():
            doc_img_path.unlink()
        if selfie_img_path and selfie_img_path.exists():
            selfie_img_path.unlink()
    except Exception as e:
        logger.error(f"Error removing image files: {e}")
        
    db.delete(record)
    db.commit()
    return {"message": f"Verification record {record_id} successfully deleted."}
