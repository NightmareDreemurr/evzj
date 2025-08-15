import requests
import base64
import logging
import io
import cv2
import numpy as np
import time
from PIL import Image
from flask import current_app
from concurrent.futures import ThreadPoolExecutor

from app.extensions import db
from app.models import PendingSubmission
from app.services.ai_matcher import match_students_for_assignment


logger = logging.getLogger(__name__)

# Suppress verbose PIL logging
pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.WARNING)

class OCRError(Exception):
    """Custom exception for OCR-related errors."""
    pass

# --- Reusable Core OCR Functions ---

def _get_access_token():
    """
    Fetches the Baidu OCR access token.
    """
    logger.debug("Fetching Baidu OCR access token...")
    token_url = current_app.config["BAIDU_OCR_TOKEN_URL"]
    params = {
        "grant_type": "client_credentials",
        "client_id": current_app.config["BAIDU_OCR_API_KEY"],
        "client_secret": current_app.config["BAIDU_OCR_SECRET_KEY"]
    }
    
    try:
        response = requests.post(token_url, params=params, timeout=5)
        response.raise_for_status()
        result = response.json()
        if "access_token" not in result:
            error_msg = result.get('error_description', 'Unknown error while fetching token')
            raise OCRError(f"Failed to get access token: {error_msg}")
        return result["access_token"]
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request to get token failed: {e}")
        raise OCRError(f"Could not get access token: {e}")

def _call_baidu_ocr_api(image_bytes, access_token):
    """
    Shared helper to call the Baidu OCR API with given image bytes and token.
    """
    encoded_string = base64.b64encode(image_bytes).decode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"image": encoded_string, "access_token": access_token}
    ocr_url = current_app.config.get("BAIDU_OCR_GENERAL_URL", "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic")
    
    logger.debug("Sending request to Baidu OCR API...")
    response = requests.post(ocr_url, headers=headers, data=data, timeout=15)
    response.raise_for_status()
    result = response.json()

    if "error_code" in result:
        error_msg = f"OCR API error [Code: {result['error_code']}]: {result.get('error_msg', 'Unknown API error')}"
        raise OCRError(error_msg)
        
    words_results = result.get("words_result", [])
    if not words_results:
        logger.warning("OCR process completed, but no text was detected.")
        return ""
        
    return "\\n".join([item["words"] for item in words_results])


# --- Legacy/Single Submission Workflow (Kept for compatibility) ---

def _compress_image_stream(image_stream, max_size_bytes=4*1024*1024, quality=85):
    """
    Compresses an image from a stream to be under a specific size. Used for single submissions.
    """
    logger.debug("Compressing image stream for single submission...")
    try:
        img = Image.open(image_stream)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.thumbnail((2048, 2048))
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        
        while buffer.tell() > max_size_bytes and quality > 10:
            quality -= 5
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)

        buffer.seek(0)
        logger.debug(f"Image compressed to {buffer.tell()} bytes.")
        return buffer.read()
    except Exception as e:
        logger.error(f"Error during image compression: {e}")
        raise OCRError(f"Image processing failed: {e}")

def recognize_text_from_image_stream(image_stream):
    """
    Recognizes text from a single image stream. This is the original function for student submissions.
    """
    logger.debug("Starting text recognition from a single image stream...")
    try:
        # 1. Compress the image (simple processing for single uploads)
        compressed_image_data = _compress_image_stream(image_stream)
        
        # 2. Get token and call API
        access_token = _get_access_token()
        recognized_text = _call_baidu_ocr_api(compressed_image_data, access_token)
        
        logger.info(f"Successfully recognized text from stream.")
        return recognized_text
    
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request to OCR service failed: {e}")
        raise OCRError(f"Could not connect to OCR service: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during single stream OCR: {e}", exc_info=True)
        raise OCRError(f"An unexpected error occurred: {e}")


# --- New Batch Processing Workflow ---

def _preprocess_image_robust(image_path: str, image_bytes: bytes) -> bytes:
    """
    Performs robust, multi-stage preprocessing on an image to maximize OCR accuracy and ensure API compliance.
    It combines OpenCV for image analysis (like deskewing) and Pillow for reliable resizing and compression.
    
    The pipeline includes:
    1.  Decoding with OpenCV for analysis.
    2.  Grayscaling and contrast enhancement using CLAHE.
    3.  Gentle deskewing to correct minor rotation.
    4.  Loading the processed image into Pillow.
    5.  Final checks and iterative compression to meet Baidu API's strict size (<4MB) and dimension (<4096px) limits.
    """
    logger.debug("Starting robust image preprocessing for batch...")
    
    try:
        # --- 1. OpenCV part: Analysis and Correction ---
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img_cv is None:
            raise OCRError("Could not decode image from bytes with OpenCV. The file may be corrupt or not a supported image format.")

        # Grayscaling and contrast enhancement
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)
        
        # Gentle deskewing
        try:
            blurred = cv2.GaussianBlur(enhanced_gray, (5, 5), 0)
            thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            coords = np.column_stack(np.where(thresh > 0))
            angle = cv2.minAreaRect(coords)[-1]
            
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            if abs(angle) > 1 and abs(angle) < 45:
                (h, w) = enhanced_gray.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                processed_cv_img = cv2.warpAffine(enhanced_gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                logger.debug(f"Corrected image skew by {angle:.2f} degrees.")
            else:
                processed_cv_img = enhanced_gray
                logger.debug(f"Image skew angle {angle:.2f} is minimal or too extreme, skipping rotation.")
        except Exception as e:
            logger.warning(f"Could not perform deskewing, proceeding without it. Error: {e}")
            processed_cv_img = enhanced_gray

        # --- 2. Pillow part: Resizing and Compression for API Compliance ---
        # Convert OpenCV image (which is a numpy array) to a Pillow image
        image = Image.fromarray(cv2.cvtColor(processed_cv_img, cv2.COLOR_GRAY2RGB))

        # Baidu OCR requires: image size < 4MB, longest edge < 4096px
        MAX_SIZE_MB = 3.9
        MAX_EDGE_LENGTH = 4095
        
        # Check and fix longest edge
        if max(image.width, image.height) > MAX_EDGE_LENGTH:
            logger.debug(f"Image edge {max(image.width, image.height)}px exceeds max {MAX_EDGE_LENGTH}px. Resizing.")
            image.thumbnail((MAX_EDGE_LENGTH, MAX_EDGE_LENGTH), Image.Resampling.LANCZOS)
            logger.debug(f"Image resized to {image.width}x{image.height}.")

        # Check and iteratively compress to fix file size
        output_buffer = io.BytesIO()
        quality = 95 # Start with high quality
        image.save(output_buffer, format="JPEG", quality=quality)
        
        while output_buffer.tell() / (1024 * 1024) > MAX_SIZE_MB and quality > 10:
            logger.debug(f"Image size {output_buffer.tell()/(1024*1024):.2f}MB exceeds {MAX_SIZE_MB}MB. Re-compressing with quality {quality-10}...")
            # Reset buffer
            output_buffer.seek(0)
            output_buffer.truncate()
            quality -= 10
            image.save(output_buffer, format="JPEG", quality=quality)
        
        if quality <= 10 and output_buffer.tell() / (1024 * 1024) > MAX_SIZE_MB:
            raise OCRError(f"Failed to compress image below {MAX_SIZE_MB}MB, even at lowest quality.")

        preprocessed_image_bytes = output_buffer.getvalue()
        final_size_kb = len(preprocessed_image_bytes) / 1024
        current_app.logger.debug(f"Image preprocessing complete. Final size: {final_size_kb:.2f} KB")

        return preprocessed_image_bytes

    except Exception as e:
        current_app.logger.error(f"Error during robust image preprocessing for '{image_path}': {e}", exc_info=True)
        # Fallback: try to return original bytes if preprocessing fails catastrophically
        return image_bytes


def _process_single_submission(pending_submission_id, app_context, access_token):
    """
    The processing pipeline for a single image in a batch, designed to be run in a thread.
    """
    with app_context:
        submission = db.session.get(PendingSubmission, pending_submission_id)
        if not submission:
            logger.error(f"Could not find PendingSubmission with id {pending_submission_id}")
            return

        try:
            submission.status = 'preprocessing'
            db.session.commit()

            # Add retry logic for file reading to handle race conditions
            image_bytes = None
            for i in range(3): # Retry up to 3 times
                try:
                    with open(submission.file_path, 'rb') as f:
                        image_bytes = f.read()
                    if image_bytes:
                        break
                except Exception as e:
                    logger.warning(f"Attempt {i+1} to read {submission.file_path} failed: {e}")
                    time.sleep(0.1) # sleep 100ms
            
            if not image_bytes:
                 raise OCRError(f"Failed to read image file after multiple retries: {submission.file_path}")

            # The new, robust preprocessing function is called here.
            preprocessed_bytes = _preprocess_image_robust(submission.file_path, image_bytes)

            submission.status = 'ocr_processing'
            db.session.commit()
            
            recognized_text = _call_baidu_ocr_api(preprocessed_bytes, access_token)
            
            submission.ocr_text = recognized_text
            submission.status = 'ocr_completed'
            logger.info(f"Successfully processed submission {submission.id}, found {len(recognized_text.splitlines())} lines.")

        except OCRError as e:
            logger.error(f"OCR Error for submission {submission.id}: {e}")
            submission.status = 'failed'
            submission.error_message = str(e)
        except Exception as e:
            logger.error(f"Unexpected Error for submission {submission.id}: {e}", exc_info=True)
            submission.status = 'failed'
            submission.error_message = "An unexpected server error occurred."
        finally:
            db.session.commit()

def process_submissions_for_assignment(assignment_id):
    """
    Main entry point for batch processing. Fetches all 'uploaded' submissions 
    for an assignment and processes them in parallel. It now triggers AI
    student matching upon completion.
    """
    app = current_app._get_current_object()
    submissions_to_process = PendingSubmission.query.filter_by(
        assignment_id=assignment_id, status='uploaded').all()

    if not submissions_to_process:
        logger.info(f"No new submissions to process for assignment {assignment_id}.")
        return

    logger.info(f"Found {len(submissions_to_process)} submissions for assignment {assignment_id}.")
    
    try:
        access_token = _get_access_token()
    except OCRError as e:
        logger.error(f"Could not get Baidu token. Aborting. Error: {e}")
        for sub in submissions_to_process:
            sub.status = 'failed'
            sub.error_message = f"Could not start task: {e}"
        db.session.commit()
        return

    max_workers = app.config.get('OCR_MAX_CONCURRENCY', 5)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(
            lambda sub_id: _process_single_submission(sub_id, app.app_context(), access_token),
            [sub.id for sub in submissions_to_process]
        )
            
    logger.info(f"Finished processing OCR batch for assignment {assignment_id}.")

    # --- NEW: Trigger the AI matcher after OCR is complete ---
    logger.info(f"Triggering AI student matching for assignment {assignment_id}...")
    try:
        match_students_for_assignment(assignment_id)
        logger.info(f"Successfully triggered AI student matching for assignment {assignment_id}.")
    except Exception as e:
        logger.error(f"An error occurred while triggering AI matcher for assignment {assignment_id}: {e}", exc_info=True)
    # --- END NEW --- 