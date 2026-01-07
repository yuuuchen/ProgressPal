# emotion/services/preprocess.py
import numpy as np
import cv2
import math
import logging
import os
import time
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile

logger = logging.getLogger(__name__)

# ===================== Config =====================
IMG_W, IMG_H = 224, 224
HAAR_DIR = cv2.data.haarcascades
FACE_CASCADE = cv2.CascadeClassifier(os.path.join(HAAR_DIR, "haarcascade_frontalface_default.xml"))
EYE_CASCADE = cv2.CascadeClassifier(os.path.join(HAAR_DIR, "haarcascade_eye.xml"))

if FACE_CASCADE.empty():
    logger.critical(f"無法載入人臉偵測模型！請檢查路徑")
    raise IOError(f"OpenCV Face Cascade load failed. Path")

if EYE_CASCADE.empty():
    logger.critical(f"無法載入眼睛偵測模型！請檢查路徑 ")

# ===================== Custom Exceptions =====================
class InvalidImageError(Exception):
    """當影像無法讀取、解碼或格式錯誤時拋出"""
    pass

class NoFaceDetectedError(Exception):
    """當影像中找不到臉、臉太小或角度過大時拋出"""
    pass

# ===================== Helper Functions =====================

def _align_by_eyes(face_gray):
    h, w = face_gray.shape
    eyes = EYE_CASCADE.detectMultiScale(face_gray, scaleFactor=1.1, minNeighbors=3, minSize=(10, 10))
    if len(eyes) < 2: 
        return face_gray
    eyes = sorted(eyes, key=lambda b: b[1])[:2]
    (x1,y1,w1,h1), (x2,y2,w2,h2) = sorted(eyes, key=lambda b: b[0])
    lc, rc = (x1 + w1//2, y1 + h1//2), (x2 + w2//2, y2 + h2//2)
    dy, dx = rc[1]-lc[1], rc[0]-lc[0]
    angle = math.degrees(math.atan2(dy, dx))
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    return cv2.warpAffine(face_gray, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)



# ===================== Main Process =====================

def preprocess_frame(uploaded_file):
    """
    主函式：接收 Django UploadedFile -> 預處理 -> Keras Model Input Format
    
    Args:
        uploaded_file: Django 的 InMemoryUploadedFile 物件 (前端上傳的圖片)
    
    Returns:
        face_final: 預處理完成的 numpy array，形狀為 (1, 224, 224, 1)
    """
    
    # # 建立 debug 資料夾
    # debug_dir = "debug_images"
    # if not os.path.exists(debug_dir):
    #     os.makedirs(debug_dir)
    
    timestamp = int(time.time())

    # -----------------------------------------------------------
    # Step 1: 讀取檔案並解碼 (關鍵除錯區)
    # 解決 Django 檔案指標與 OpenCV 解碼相容性問題
    # -----------------------------------------------------------

    try:
        # [Step A] 強制重置檔案指標 (Fix file pointer issue)
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
            
        # [Step B] 讀取 Bytes
        file_content = uploaded_file.read()
        file_size = len(file_content)
        logger.info(f"Preprocess received file size: {file_size} bytes")

        if file_size == 0:
            raise InvalidImageError("讀取到的檔案大小為 0，可能是前端上傳失敗或指標錯誤")

        # [Step C] 將收到的原始 Bytes 存檔 (數位鑑識)
        # 檢查這張圖：如果這張是黑的，代表 views.py 傳進來就是黑的
        # raw_filename = f"{debug_dir}/step1_raw_input_{timestamp}.jpg"
        # with open(raw_filename, "wb") as f:
        #     f.write(file_content)
        
        # [Step D] 解碼
        np_arr = np.frombuffer(file_content, np.uint8)
        frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame_bgr is None:
            logger.error("cv2.imdecode returned None. Image format might be invalid.")
            raise InvalidImageError("無法解碼影像")

        # # [Step E] 檢查解碼後的亮度
        # avg_brightness = np.mean(frame_bgr)
        # logger.info(f"Decoded Image Brightness: {avg_brightness:.2f}")
        
        # # 存下解碼後的圖
        # # 如果 raw 是好的，但這張是黑的，代表 OpenCV 解碼有問題
        # decoded_filename = f"{debug_dir}/step2_decoded_{timestamp}.jpg"
        # cv2.imwrite(decoded_filename, frame_bgr)

        # if avg_brightness < 5:
        #     logger.warning("警告：解碼後的影像極暗 (全黑)")

    except Exception as e:
        logger.error(f"Image read error: {e}")
        raise InvalidImageError(f"讀取影像失敗: {e}")

    logger.info("Info: 影像讀取與解碼成功")
    
    h_img, w_img, _ = frame_bgr.shape


    # -----------------------------------------------------------
    # Step 2: 臉部偵測 (Haar Cascade)+灰階
    # -----------------------------------------------------------
    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
   
    results = FACE_CASCADE.detectMultiScale(frame_gray, 1.1, 5, minSize=(60,60))
    if len(results) == 0:
        raise NoFaceDetectedError("no face")

    # 取信心度最高的一張臉
    x,y,w,h = max(results, key=lambda b:b[2]*b[3])
    roi = frame_gray[y:y+h, x:x+w]
    
    # -----------------------------------------------------------
    # Step 3: 裁切 (Crop Face ROI)、 Resize
    # -----------------------------------------------------------
    aligned = _align_by_eyes(roi)    
    # -----------------------------------------------------------
    # Step 4: Resize & Normalize (Model Prep)
    # -----------------------------------------------------------
    try:
        resized = cv2.resize(aligned, (IMG_W, IMG_H), interpolation=cv2.INTER_AREA)
    except Exception:
        raise NoFaceDetectedError("Resize failed")

    # 轉換格式給模型 (1, 224, 224, 1)
    # 1. 轉 float32
    # 2. 增加通道維度 (H, W) -> (H, W, 1)
    # 3. 增加 Batch 維度 (H, W, 1) -> (1, H, W, 1)
    face_res = resized.astype(np.float32)[..., None]
    face_final = np.expand_dims(face_res, axis=0)

    return face_final