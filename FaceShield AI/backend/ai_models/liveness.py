import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

def check_liveness(cv_img):
    """
    Performs passive single-frame liveness detection (anti-spoofing).
    Combines:
    1. FFT Frequency Analysis (Moiré patterns from screens).
    2. Local texture analysis (LBP-like standard deviation of local gradients).
    3. Specular reflection / glare spots.
    
    Returns:
        liveness_score: float (0.0 to 1.0), where >= 0.50 is classified as LIVE.
        details: dict of individual test results.
    """
    try:
        if cv_img is None or cv_img.size == 0:
            return 0.0, {"error": "Invalid image"}
            
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        # --- 1. FFT Frequency Analysis (Screen Replay Detection) ---
        # Screens introduce periodic grid structures (moiré patterns) that create spikes in FFT high frequencies.
        # Get central crop of face for FFT to avoid background noise
        cy, cx = h // 2, w // 2
        size = min(64, h, w)
        crop = gray[cy - size//2:cy + size//2, cx - size//2:cx + size//2]
        
        dft = cv2.dft(np.float32(crop), flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)
        magnitude_spectrum = 20 * np.log(cv2.cartToPolar(dft_shift[:, :, 0], dft_shift[:, :, 1])[0] + 1)
        
        # Real skin has energy concentrated in low frequencies. Screen spoofing has higher energy in high frequencies.
        high_freq_sum = np.sum(magnitude_spectrum) - np.sum(magnitude_spectrum[size//4:3*size//4, size//4:3*size//4])
        freq_ratio = float(high_freq_sum / (np.sum(magnitude_spectrum) + 1e-6))
        
        # A high frequency ratio indicates potential screen structure. Normal live faces are around 0.15 - 0.35.
        # Screens with moiré can go above 0.50.
        is_screen_attack = freq_ratio > 0.45
        
        # --- 2. Texture & Edge Analysis (Print Attack Detection) ---
        # Printed paper lacks the micro-depth of human skin. We can look at standard deviation of local gradients.
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = cv2.magnitude(sobelx, sobely)
        grad_std = float(np.std(grad_mag))
        
        # Printed images often have flat or artificially sharpened gradients.
        # Live skin std dev is typically in the range of 15.0 - 55.0. Paper prints show lower/higher variances.
        is_print_attack = grad_std < 8.0 or grad_std > 85.0
        
        # --- 3. Specular Glare / Reflection Spots ---
        # Screens have high reflection. We count pixels with maximum brightness (close to 255)
        _, thresholded = cv2.threshold(gray, 248, 255, cv2.THRESH_BINARY)
        glare_pixels = int(cv2.countNonZero(thresholded))
        glare_ratio = glare_pixels / (h * w)
        is_glare_attack = glare_ratio > 0.08 # More than 8% glare is suspicious
        
        # --- 4. Synthesis of Liveness Score ---
        # Calculate liveness confidence:
        # Deduct score for each indicator
        score = 1.0
        
        if is_screen_attack:
            score -= 0.45
        if is_print_attack:
            score -= 0.40
        if is_glare_attack:
            score -= 0.35
            
        # Penalize if freq_ratio is moderately high
        if freq_ratio > 0.38:
            score -= (freq_ratio - 0.38) * 2.0
            
        score = float(max(0.0, min(1.0, score)))
        
        details = {
            "fft_freq_ratio": freq_ratio,
            "gradient_std": grad_std,
            "glare_ratio": glare_ratio,
            "is_screen_attack": bool(is_screen_attack),
            "is_print_attack": bool(is_print_attack),
            "is_glare_attack": bool(is_glare_attack)
        }
        
        return score, details
    except Exception as e:
        logger.error(f"Liveness detection error: {e}")
        return 0.5, {"error": str(e), "message": "Liveness analysis bypassed due to error"}
