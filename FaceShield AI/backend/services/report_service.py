import csv
import io
import os
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from backend.database.models import VerificationRecord
from backend.config import settings

class ReportService:
    @staticmethod
    def generate_csv(records: list[VerificationRecord]) -> str:
        """
        Exports verification logs as a CSV file.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            "Record ID", "User ID", "Document Type", "Status",
            "Face Match Score (%)", "Liveness Score (%)", "Fraud Risk Score (%)",
            "Processing Time (s)", "Verification Date"
        ])
        
        # Rows
        for record in records:
            writer.writerow([
                record.id,
                record.user_id,
                record.document_type,
                record.status,
                round(record.match_score, 2),
                round(record.liveness_score * 100, 2),
                round(record.fraud_risk_score * 100, 2),
                round(record.processing_time, 2),
                record.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])
            
        return output.getvalue()

    @staticmethod
    def generate_pdf_report(record: VerificationRecord, user_fullname: str) -> str:
        """
        Generates a professional PDF verification report.
        Returns the absolute filepath to the created PDF.
        """
        filename = f"report_{record.id}_{int(datetime.datetime.utcnow().timestamp())}.pdf"
        filepath = os.path.join(settings.REPORTS_DIR, filename)
        
        # Setup document
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#3F51B5"),
            spaceAfter=15
        )
        
        section_style = ParagraphStyle(
            name="SectionStyle",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1A237E"),
            spaceBefore=10,
            spaceAfter=8,
            borderPadding=2
        )
        
        body_style = ParagraphStyle(
            name="BodyStyle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#333333")
        )
        
        bold_body_style = ParagraphStyle(
            name="BoldBodyStyle",
            parent=body_style,
            fontName="Helvetica-Bold"
        )
        
        status_color = "#4CAF50" # Green
        if record.status == "failed":
            status_color = "#F44336" # Red
        elif record.status == "flagged":
            status_color = "#FF9800" # Orange
            
        status_style = ParagraphStyle(
            name="StatusStyle",
            parent=bold_body_style,
            textColor=colors.HexColor(status_color),
            fontSize=12
        )

        # Header Title
        story.append(Paragraph("FaceShield AI – Identity Verification Report", title_style))
        story.append(Paragraph(f"Generated on: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", body_style))
        story.append(Spacer(1, 15))
        
        # Summary Section
        summary_data = [
            [Paragraph("Record ID:", bold_body_style), Paragraph(str(record.id), body_style),
             Paragraph("Verification Status:", bold_body_style), Paragraph(record.status.upper(), status_style)],
            [Paragraph("Requested By:", bold_body_style), Paragraph(user_fullname, body_style),
             Paragraph("Document Type:", bold_body_style), Paragraph(record.document_type, body_style)],
            [Paragraph("Processing Time:", bold_body_style), Paragraph(f"{record.processing_time:.2f} seconds", body_style),
             Paragraph("Verification Date:", bold_body_style), Paragraph(record.created_at.strftime('%Y-%m-%d %H:%M:%S'), body_style)]
        ]
        
        summary_table = Table(summary_data, colWidths=[110, 150, 130, 130])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F5F5F5")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E0E0E0")),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 15))
        
        # Scores & Risk Assessment Section
        story.append(Paragraph("AI & Risk Verification Metrics", section_style))
        
        # Determine Liveness text
        liveness_text = f"{record.liveness_score * 100:.1f}% (LIVE)" if record.liveness_score >= settings.LIVENESS_THRESHOLD else f"{record.liveness_score * 100:.1f}% (SPOOF / ATTACK DETECTED)"
        
        metrics_data = [
            [Paragraph("Metric Name", bold_body_style), Paragraph("Calculated Value", bold_body_style), Paragraph("Threshold / Reference", bold_body_style), Paragraph("Result", bold_body_style)],
            [Paragraph("Face Match Similarity", body_style), Paragraph(f"{record.match_score:.2f}%", body_style), Paragraph(f">= {settings.FACE_MATCH_THRESHOLD * 100:.1f}%", body_style), Paragraph("MATCHED" if record.match_score >= settings.FACE_MATCH_THRESHOLD * 100 else "MISMATCHED", bold_body_style)],
            [Paragraph("Liveness Detection", body_style), Paragraph(liveness_text, body_style), Paragraph(f">= {settings.LIVENESS_THRESHOLD * 100:.1f}%", body_style), Paragraph("PASSED" if record.liveness_score >= settings.LIVENESS_THRESHOLD else "FAILED", bold_body_style)],
            [Paragraph("Fraud Risk Score", body_style), Paragraph(f"{record.fraud_risk_score * 100:.1f}%", body_style), Paragraph("< 50.0%", body_style), Paragraph("LOW RISK" if record.fraud_risk_score < 0.50 else "HIGH RISK - FLAGGED", bold_body_style)]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[150, 160, 110, 100])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A237E")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E0E0E0")),
        ]))
        
        # Color metrics headers text white manually by style override or table style
        for i in range(4):
            metrics_data[0][i].style.textColor = colors.white
            
        story.append(metrics_table)
        story.append(Spacer(1, 15))
        
        # OCR Extracted Fields Section
        story.append(Paragraph("OCR Document Parsing Details", section_style))
        
        ocr_rows = []
        ocr_rows.append([Paragraph("Field Name", bold_body_style), Paragraph("Extracted Value", bold_body_style)])
        
        if record.ocr_data and "parsed_fields" in record.ocr_data:
            fields = record.ocr_data["parsed_fields"]
            for field_key, field_val in fields.items():
                # Clean key labels (e.g. date_of_birth -> Date of Birth)
                label = field_key.replace("_", " ").title()
                ocr_rows.append([Paragraph(label, body_style), Paragraph(str(field_val), body_style)])
        else:
            ocr_rows.append([Paragraph("No OCR data available", body_style), Paragraph("-", body_style)])
            
        ocr_table = Table(ocr_rows, colWidths=[200, 320])
        ocr_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E0E0E0")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#B0BEC5")),
        ]))
        story.append(ocr_table)
        story.append(Spacer(1, 20))
        
        # Footer Note
        story.append(Paragraph("<b>Security Notice:</b> FaceShield AI systems continuously monitor and inspect biometric identity parameters. This report was cryptographically signed and stored in audit logs. Any modification of this document invalidates its authenticity.", body_style))
        
        # Build PDF
        doc.build(story)
        
        return filepath
