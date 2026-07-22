import cv2
import easyocr
import re
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self):
        try:
            # Initialize EasyOCR reader for English
            # We can download weights automatically on first run
            self.reader = easyocr.Reader(['en'], gpu=False) # Use CPU for maximum compatibility
            self.ocr_loaded = True
            logger.info("EasyOCR loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}. Running with mock OCR fallback.")
            self.ocr_loaded = False

    def detect_qr_code(self, cv_img):
        """
        Detects and decodes QR codes using OpenCV's built-in detector.
        """
        try:
            detector = cv2.QRCodeDetector()
            val, points, straight_qrcode = detector.detectAndDecode(cv_img)
            if val:
                logger.info(f"QR Code detected: {val[:40]}...")
                return val
        except Exception as e:
            logger.error(f"QR Code detection error: {e}")
        return None

    def extract_text(self, cv_img):
        """
        Extracts raw text blocks and strings from the image.
        """
        if not self.ocr_loaded:
            return ["FACESHIELD MOCK DOCUMENT", "NAME: JOHN DOE", "NUMBER: 1234 5678 9012", "DOB: 01/01/1990", "GENDER: MALE"]

        try:
            # Optimize image for OCR
            # Gray conversion
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            
            # Run OCR
            results = self.reader.readtext(gray, detail=0)
            logger.info(f"OCR extracted {len(results)} text snippets.")
            return results
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return []

    def parse_document(self, cv_img, doc_type):
        """
        Parses extracted OCR text based on document type.
        Supports: 'Aadhaar', 'PAN', 'Passport', 'Driving License', 'Voter ID'
        """
        text_lines = self.extract_text(cv_img)
        qr_data = self.detect_qr_code(cv_img)
        
        full_text = " \n ".join(text_lines)
        logger.info(f"Parsing document text (length: {len(full_text)}) for type: {doc_type}")
        
        result = {
            "document_type": doc_type,
            "extracted_text": text_lines,
            "qr_code": qr_data,
            "parsed_fields": {}
        }
        
        fields = {}
        
        # General helpers
        dob_match = re.search(r'(\d{2}/\d{2}/\d{4})|(\d{2}-\d{2}-\d{4})', full_text)
        if dob_match:
            fields["date_of_birth"] = dob_match.group(0)
            
        gender_match = re.search(r'\b(MALE|FEMALE|Male|Female|M|F)\b', full_text, re.IGNORECASE)
        if gender_match:
            g = gender_match.group(0).upper()
            fields["gender"] = "Male" if g.startswith("M") else "Female"

        # Document specific regex parser
        if doc_type == "Aadhaar":
            # Aadhaar number format: 12 digits (often spaced as xxxx xxxx xxxx)
            aadhaar_match = re.search(r'\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b', full_text)
            if aadhaar_match:
                fields["aadhaar_number"] = aadhaar_match.group(0)
            
            # Attempt to extract name (usually first line that contains only characters and is capitalized)
            # Standard Aadhaar format has Government details, then NAME, then DOB, then Gender
            name_lines = []
            for line in text_lines:
                line_clean = line.strip()
                if len(line_clean) > 3 and not any(char.isdigit() for char in line_clean) and "Government" not in line_clean and "India" not in line_clean:
                    name_lines.append(line_clean)
            if name_lines:
                # Name is usually the first clean string after removing institutional words
                fields["name"] = name_lines[0]

        elif doc_type == "PAN":
            # PAN Card format: 5 letters, 4 numbers, 1 letter (e.g. ABCDE1234F)
            pan_match = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', full_text.upper())
            if pan_match:
                fields["pan_number"] = pan_match.group(0)
            
            # PAN structure: INCOME TAX DEPARTMENT, Name, Father's Name, DOB
            # Clean up headers
            clean_lines = [l.strip() for l in text_lines if not any(w in l.upper() for w in ["INCOME", "TAX", "DEPARTMENT", "GOVT", "INDIA", "CARD"])]
            valid_names = [l for l in clean_lines if len(l) > 3 and not any(c.isdigit() for c in l)]
            
            if len(valid_names) >= 1:
                fields["name"] = valid_names[0]
            if len(valid_names) >= 2:
                fields["father_name"] = valid_names[1]

        elif doc_type == "Passport":
            # Passport format: Letter followed by 7 digits (e.g. Z1234567)
            passport_match = re.search(r'\b[A-Z][0-9]{7}\b', full_text.upper())
            if passport_match:
                fields["passport_number"] = passport_match.group(0)
                
            # Passport details: Surname, Given Name(s)
            surname_idx = -1
            given_name_idx = -1
            for idx, line in enumerate(text_lines):
                if "SURNAME" in line.upper():
                    surname_idx = idx
                if "GIVEN NAME" in line.upper() or "GIVEN" in line.upper():
                    given_name_idx = idx
                    
            if surname_idx != -1 and surname_idx + 1 < len(text_lines):
                fields["surname"] = text_lines[surname_idx + 1]
            if given_name_idx != -1 and given_name_idx + 1 < len(text_lines):
                fields["given_name"] = text_lines[given_name_idx + 1]
                
            if "surname" in fields and "given_name" in fields:
                fields["name"] = f"{fields['given_name']} {fields['surname']}"

        elif doc_type == "Driving License":
            # DL Format: State code (2 letters) + 13 digits, spaced or hyphenated
            dl_match = re.search(r'\b[A-Z]{2}[-\s]?[0-9]{2,4}[-\s]?[0-9]{7,11}\b', full_text.upper())
            if dl_match:
                fields["dl_number"] = dl_match.group(0)
            
            # Extract name and expiry if present
            exp_match = re.search(r'(?:VALID|EXPIRY|EXP|UPTO)[:\s]+(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
            if exp_match:
                fields["expiry_date"] = exp_match.group(1)
                
            valid_names = [l.strip() for l in text_lines if len(l.strip()) > 3 and not any(c.isdigit() for c in l) and not any(w in l.upper() for w in ["DRIVING", "LICENSE", "STATE", "UNION", "TRANSPORT"])]
            if valid_names:
                fields["name"] = valid_names[0]

        elif doc_type == "Voter ID":
            # EPIC Number (Voter ID): 3 letters followed by 7 digits
            epic_match = re.search(r'\b[A-Z]{3}[0-9]{7}\b', full_text.upper())
            if epic_match:
                fields["epic_number"] = epic_match.group(0)
                
            # ELECTION COMMISSION OF INDIA, Name, Father's/Husband's Name
            valid_names = [l.strip() for l in text_lines if len(l.strip()) > 3 and not any(c.isdigit() for c in l) and not any(w in l.upper() for w in ["ELECTION", "COMMISSION", "INDIA", "VOTER", "IDENTITY"])]
            if len(valid_names) >= 1:
                fields["name"] = valid_names[0]
            if len(valid_names) >= 2:
                fields["relation_name"] = valid_names[1]

        # Fill default placeholders for fields not extracted
        if "name" not in fields:
            # Fallback to the first alphabetic-only line of text
            alpha_lines = [l.strip() for l in text_lines if len(l.strip()) > 4 and re.match(r'^[A-Za-z\s]+$', l.strip())]
            if alpha_lines:
                fields["name"] = alpha_lines[0]
            else:
                fields["name"] = "Not Detected"
                
        if "date_of_birth" not in fields:
            fields["date_of_birth"] = "Not Detected"
            
        if "gender" not in fields:
            fields["gender"] = "Not Detected"

        # Apply specific fields
        result["parsed_fields"] = fields
        return result

# Instantiate singleton engine
ocr_engine = OCREngine()
