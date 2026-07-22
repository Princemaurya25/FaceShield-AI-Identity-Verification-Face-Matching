import cv2
import numpy as np
import torch
from PIL import Image
import os
import math
import logging
from facenet_pytorch import MTCNN, InceptionResnetV1
from backend.config import settings

logger = logging.getLogger(__name__)

class AIEngine:
    def __init__(self):
        # Determine device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"AI Engine loading on device: {self.device}")
        
        try:
            # Initialize MTCNN for face detection and landmark generation
            self.mtcnn = MTCNN(
                keep_all=False, 
                post_process=False, 
                device=self.device,
                min_face_size=40,
                thresholds=[0.6, 0.7, 0.7]
            )
            # Initialize InceptionResnetV1 pre-trained on VGGFace2 for embeddings
            self.resnet = InceptionResnetV1(pretrained='vggface2', device=self.device).eval()
            self.models_loaded = True
            logger.info("MTCNN and FaceNet models loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load AI models: {e}. Running with mocked fallback embeddings.")
            self.models_loaded = False

    def detect_face(self, cv_img):
        """
        Detects a face in the image and returns bounding box and landmarks.
        """
        if not self.models_loaded:
            # Mock face detection
            h, w = cv_img.shape[:2]
            return [0, 0, w, h], None
            
        try:
            # Convert OpenCV image (BGR) to PIL Image (RGB)
            rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_img)
            
            # Detect boxes, probabilities and landmarks
            boxes, probs, landmarks = self.mtcnn.detect(pil_img, landmarks=True)
            
            if boxes is not None and len(boxes) > 0:
                # Get the highest probability face
                best_idx = np.argmax(probs)
                if probs[best_idx] > 0.85: # Confidence threshold
                    return boxes[best_idx], landmarks[best_idx]
            
            return None, None
        except Exception as e:
            logger.error(f"Error in face detection: {e}")
            return None, None

    def align_and_crop_face(self, cv_img, box, landmarks):
        """
        Aligns the face geometrically based on eye landmarks and crops it.
        """
        try:
            if landmarks is None:
                # If no landmarks, just crop using box
                x1, y1, x2, y2 = [max(0, int(c)) for c in box]
                cropped = cv_img[y1:y2, x1:x2]
                if cropped.size == 0:
                    return cv_img
                return cv_img[y1:y2, x1:x2]
                
            # Landmarks: [left_eye, right_eye, nose, mouth_left, mouth_right]
            left_eye = landmarks[0]
            right_eye = landmarks[1]
            
            # Calculate angle between eyes
            dY = right_eye[1] - left_eye[1]
            dX = right_eye[0] - left_eye[0]
            angle = np.degrees(np.arctan2(dY, dX))
            
            # Center of rotation is the midpoint between eyes
            eye_center = (
                int((left_eye[0] + right_eye[0]) / 2),
                int((left_eye[1] + right_eye[1]) / 2)
            )
            
            # Rotation matrix
            h, w = cv_img.shape[:2]
            M = cv2.getRotationMatrix2D(eye_center, angle, scale=1.0)
            
            # Perform rotation
            rotated = cv2.warpAffine(cv_img, M, (w, h), flags=cv2.INTER_CUBIC)
            
            # Rotate the bounding box points to crop the aligned image
            x1, y1, x2, y2 = [int(c) for c in box]
            
            # Apply padding margin
            width = x2 - x1
            height = y2 - y1
            pad_x = int(width * 0.15)
            pad_y = int(height * 0.15)
            
            rx1 = max(0, x1 - pad_x)
            ry1 = max(0, y1 - pad_y)
            rx2 = min(w, x2 + pad_x)
            ry2 = min(h, y2 + pad_y)
            
            cropped = rotated[ry1:ry2, rx1:rx2]
            if cropped.size == 0:
                return cv_img
                
            return cropped
        except Exception as e:
            logger.error(f"Error in face alignment: {e}")
            # Fallback to simple crop
            try:
                x1, y1, x2, y2 = [max(0, int(c)) for c in box]
                return cv_img[y1:y2, x1:x2]
            except:
                return cv_img

    def get_face_embedding(self, cv_face_img):
        """
        Generates 512-dimensional embedding using FaceNet.
        """
        if not self.models_loaded:
            # Return a mock embedding vector based on mean color
            avg_color = cv_face_img.mean(axis=(0,1))
            mock_emb = np.zeros(512)
            mock_emb[:3] = avg_color / 255.0
            return mock_emb / np.linalg.norm(mock_emb)

        try:
            # Resize image to model expected size (160x160)
            face_resized = cv2.resize(cv_face_img, (160, 160))
            # BGR to RGB
            face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
            
            # Normalize to [-1, 1] as expected by FaceNet
            face_np = face_rgb.astype(np.float32)
            face_np = (face_np - 127.5) / 128.0
            
            # HWC to CHW
            face_tensor = torch.tensor(face_np).permute(2, 0, 1).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                embedding = self.resnet(face_tensor)
                
            embedding_np = embedding.squeeze().cpu().numpy()
            # Normalize embedding
            embedding_np = embedding_np / np.linalg.norm(embedding_np)
            return embedding_np
        except Exception as e:
            logger.error(f"Error generating face embedding: {e}")
            return None

    def calculate_similarity(self, emb1, emb2):
        """
        Calculates cosine similarity between two embeddings.
        Returns similarity score and match boolean.
        """
        if emb1 is None or emb2 is None:
            return 0.0, False
            
        # Cosine Similarity = dot(A, B) / (||A|| * ||B||)
        # Since they are normalized, it is just dot(A, B)
        similarity = float(np.dot(emb1, emb2))
        
        # InceptionResnetV1 cosine similarity threshold is typically 0.60 to 0.65
        is_match = similarity >= settings.FACE_MATCH_THRESHOLD
        
        # Scale score from [-1, 1] to [0, 100]% for user display
        display_score = max(0.0, min(100.0, (similarity + 1.0) / 2.0 * 100.0))
        
        return display_score, is_match

    def assess_face_quality(self, cv_img):
        """
        Assess Face Quality: Blur, brightness, and resolution checks.
        """
        # 1. Blur Detection (Laplacian variance)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        is_blurry = blur_score < 100.0 # Standard threshold
        
        # 2. Brightness Check
        brightness = float(np.mean(gray))
        is_poor_lighting = brightness < 40.0 or brightness > 230.0
        
        # Quality score out of 1.0
        quality_score = 1.0
        if is_blurry:
            quality_score -= 0.4
        if is_poor_lighting:
            quality_score -= 0.3
            
        # Add a tiny noise factor for realistic precision
        quality_score = max(0.1, min(1.0, quality_score))
        
        return {
            "blur_score": float(blur_score),
            "brightness": brightness,
            "is_blurry": bool(is_blurry),
            "is_poor_lighting": bool(is_poor_lighting),
            "quality_score": float(quality_score)
        }

# Instantiate singleton engine
ai_engine = AIEngine()
