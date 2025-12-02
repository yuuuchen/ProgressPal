# emotion/services/preprocess.py
import numpy as np
import cv2
import math
import logging
import mediapipe as mp
import os
import time
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile

logger = logging.getLogger(__name__)

# ===================== Config =====================
IMG_W, IMG_H = 224, 224 # 模型輸入的影像尺寸
MIN_FACE_SIZE = 40  # 臉部最小寬度 (像素)，小於此數值視為雜訊或誤判      
BLUR_THRESHOLD = 30  # 模糊檢測閾值 (Laplacian 變異數)  越小越寬容    
POSE_THRESHOLD_RATIO = 2.5  # 轉頭容忍度 (鼻眼距離比值)，過濾掉側臉

# 初始化 MediaPipe (使用適合 Webcam 的 model_selection=0)
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)

# ===================== Custom Exceptions =====================
class InvalidImageError(Exception):
    """當影像無法讀取、解碼或格式錯誤時拋出"""
    pass

class NoFaceDetectedError(Exception):
    """當影像中找不到臉、臉太小或角度過大時拋出"""
    pass

# ===================== Helper Functions =====================
def check_head_pose(keypoints, img_w):
    """
    檢查頭部轉動角度 (Head Pose Estimation)
    透過比較鼻子到左右眼的水平距離比例，來判斷是否為側臉。
    """
    # 取得關鍵點的 X 座標 (正規化座標轉為像素座標)
    right_eye_x = keypoints[0].x * img_w
    left_eye_x = keypoints[1].x * img_w
    nose_x = keypoints[2].x * img_w

    # 基本檢核：鼻子必須在兩眼之間
    if not (right_eye_x < nose_x < left_eye_x):
        return False

    dist_right = abs(nose_x - right_eye_x)
    dist_left = abs(nose_x - left_eye_x)

    if dist_right == 0 or dist_left == 0:
        return False
    
    # 計算比例 (大於閾值代表轉頭過度)
    ratio = dist_left / dist_right
    if ratio > POSE_THRESHOLD_RATIO or ratio < (1.0 / POSE_THRESHOLD_RATIO):
        return False 
    return True

def check_blurriness(img_gray):
    """
    檢查影像模糊度 (Blur Detection)
    使用 Laplacian 算子的變異數 (Variance) 來評估清晰度。
    變異數越高代表邊緣越銳利 (清晰)；越低代表越模糊。
    """
    variance = cv2.Laplacian(img_gray, cv2.CV_64F).var()
    return variance > BLUR_THRESHOLD

def align_face(face_img, angle):
    """
    臉部旋轉對齊 (Face Alignment)
    根據計算出的角度，將臉部旋轉至水平。
    """
    h, w = face_img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    aligned = cv2.warpAffine(face_img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return aligned

def get_rotation_angle(keypoints, img_w, img_h):
    """
    計算旋轉角度
    根據左右眼的連線計算與水平線的夾角。
    """
    right_eye = keypoints[0] 
    left_eye = keypoints[1]  
    # 轉換為像素座標
    re_x, re_y = int(right_eye.x * img_w), int(right_eye.y * img_h)
    le_x, le_y = int(left_eye.x * img_w), int(left_eye.y * img_h)
    # 計算斜率與角度
    dy = le_y - re_y
    dx = le_x - re_x
    return math.degrees(math.atan2(dy, dx))

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
    # Step 2: 臉部偵測 (MediaPipe)
    # -----------------------------------------------------------
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    # frame_rgb = cv2.flip(frame_rgb, 1) # 暫時註解翻轉，先確保圖片內容正確最重要
    
    results = face_detection.process(frame_rgb)
    
    if not results.detections:
        raise NoFaceDetectedError("未偵測到臉部")

    # 取信心度最高的一張臉
    detection = results.detections[0]
    bboxC = detection.location_data.relative_bounding_box
    keypoints = detection.location_data.relative_keypoints

    # -----------------------------------------------------------
    # Step 3 & 4: 轉頭檢測與角度計算
    # -----------------------------------------------------------
    if not check_head_pose(keypoints, w_img):
        logger.warning("Info: 轉頭角度過大")
        raise NoFaceDetectedError("臉部角度過大 (側臉)")

    # 計算角度
    try:
        angle = get_rotation_angle(keypoints, w_img, h_img)
    except Exception:
        angle = 0

    # 裁切座標
    x = int(bboxC.xmin * w_img)
    y = int(bboxC.ymin * h_img)
    w = int(bboxC.width * w_img)
    h = int(bboxC.height * h_img)
    # 座標防呆 (確保裁切框在圖片範圍內)
    x = max(0, x)
    y = max(0, y)
    w = min(w, w_img - x)
    h = min(h, h_img - y)
    
    if w < 30 or h < 30: 
        logger.warning(f"Face too small: {w}x{h}")
        raise NoFaceDetectedError("臉部過小或邊界框無效")

    # -----------------------------------------------------------
    # Step 5: 裁切 (Crop Face ROI)
    # -----------------------------------------------------------
    face_crop_bgr = frame_bgr[y:y+h, x:x+w]
    
    # -----------------------------------------------------------
    # Step 6: 轉灰階 (Grayscale Conversion)
    # -----------------------------------------------------------
    face_gray = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2GRAY)

    # -----------------------------------------------------------
    # Step 7: 模糊檢測 (Blur Check)
    # -----------------------------------------------------------
    if not check_blurriness(face_gray):
        # 為了除錯，先不擋模糊，改為印出警告
        logger.warning("Info: 影像模糊，但在除錯模式下繼續")
        # return None # Debug 期間先註解掉，確保能產出結果
    
    # -----------------------------------------------------------
    # Step 8: 對齊 (Align)
    # -----------------------------------------------------------
    aligned = align_face(face_gray, angle)

    # -----------------------------------------------------------
    # Step 9: Resize & Normalize (Model Prep)
    # -----------------------------------------------------------
    try:
        resized = cv2.resize(aligned, (IMG_W, IMG_H), interpolation=cv2.INTER_AREA)
    except Exception:
        raise NoFaceDetectedError("Resize failed")

    # 轉換格式給模型 (1, 224, 224, 1)
    # 1. 轉 float32
    # 2. 增加通道維度 (H, W) -> (H, W, 1)
    # 3. 正規化 (0~255 -> 0~1)
    # 4. 增加 Batch 維度 (H, W, 1) -> (1, H, W, 1)
    face_res = resized.astype(np.float32)[..., None]
    # face_res = face_res / 255.0
    face_final = np.expand_dims(face_res, axis=0)

    return face_final