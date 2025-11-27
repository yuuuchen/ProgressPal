# emotion/services/preprocess.py
"""
預處理流程 (Quality Gate Optimized Version)：
1. 接收前端上傳影像
2. MediaPipe 臉部偵測 (取得關鍵點)
3. [新增] 轉頭檢測：過濾掉角度過大的側臉
4. 計算旋轉角度 (雙眼連線)
5. 裁切臉部 ROI
6. 轉灰階
7. [新增] 模糊檢測：過濾掉太模糊的影像
8. 臉部對齊 (依計算出的角度旋轉)
9. resize (224x224) → normalization (/255) → shape (1, 224, 224, 1)
"""

import numpy as np
import cv2
import math
import mediapipe as mp
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile

# ===================== Config =====================
IMG_W, IMG_H = 224, 224

# 品質過濾參數
MIN_FACE_SIZE = 40          # 臉部最小寬度 (像素)
BLUR_THRESHOLD = 30         # 模糊閾值 (越小越寬容，一般設 50~100)
POSE_THRESHOLD_RATIO = 2.5  # 轉頭容忍度 (鼻眼距離比值，越大越寬容)

# 初始化 MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
# model_selection=0 適合近距離 (筆電前學習場景)
face_detection = mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)

# ===================== Custom Exceptions =====================
class InvalidImageError(Exception):
    """圖片格式無法解析（不是合法影像）"""
    pass

class NoFaceDetectedError(Exception):
    """沒有偵測到臉部"""
    pass

# ===================== Helper Functions =====================
def check_head_pose(keypoints, img_w):
    """
    檢查是否為側臉 (Head Pose Check)
    邏輯：檢查鼻尖是否在雙眼之間，且距離比例不過度懸殊
    回傳: True (是正臉), False (是側臉)
    """
    # Keypoints: 0=右眼, 1=左眼, 2=鼻尖
    right_eye_x = keypoints[0].x * img_w
    left_eye_x = keypoints[1].x * img_w
    nose_x = keypoints[2].x * img_w

    # 1. 鼻尖必須在兩眼之間 (基本物理限制)
    # 注意：圖片座標中，右眼在左側(x小)，左眼在右側(x大)
    if not (right_eye_x < nose_x < left_eye_x):
        return False

    # 2. 計算對稱性 (鼻尖到兩眼的距離比)
    dist_right = abs(nose_x - right_eye_x)
    dist_left = abs(nose_x - left_eye_x)

    # 避免除以 0
    if dist_right == 0 or dist_left == 0:
        return False

    ratio = dist_left / dist_right

    # 如果比例大於閾值 (ex: 2.5) 或小於倒數 (ex: 1/2.5=0.4)，代表頭轉太偏
    if ratio > POSE_THRESHOLD_RATIO or ratio < (1.0 / POSE_THRESHOLD_RATIO):
        return False # 轉頭太過分了

    return True # 通過檢查

def check_blurriness(img_gray):
    """
    檢查圖片模糊程度 (Variance of Laplacian)
    回傳: True (清晰), False (模糊)
    """
    variance = cv2.Laplacian(img_gray, cv2.CV_64F).var()
    # print(f"Blur Variance: {variance}") # 除錯用
    return variance > BLUR_THRESHOLD

def get_rotation_angle(keypoints, img_w, img_h):
    """
    從 MediaPipe 的關鍵點計算雙眼連線的旋轉角度
    MediaPipe Keypoints 索引: 0=右眼, 1=左眼 (以人臉視角)
    """
    # 取得左右眼座標 (MediaPipe 給的是相對座標 0~1，需轉回像素座標)
    # keypoints[0] 是右眼 (Right Eye)，keypoints[1] 是左眼 (Left Eye)
    # 注意：這裡的左右是「對方的左右」，所以在圖片上，右眼通常在左邊 (x較小)，左眼在右邊 (x較大)
    
    right_eye = keypoints[0] # 人的右眼 (畫面左側)
    left_eye = keypoints[1]  # 人的左眼 (畫面右側)

    re_x, re_y = int(right_eye.x * img_w), int(right_eye.y * img_h)
    le_x, le_y = int(left_eye.x * img_w), int(left_eye.y * img_h)

    # 計算角度 (dy/dx)
    dy = le_y - re_y
    dx = le_x - re_x
    angle = math.degrees(math.atan2(dy, dx))
    
    return angle

def align_face(face_img, angle):
    """
    根據傳入的角度旋轉圖片
    """
    h, w = face_img.shape[:2] # 支援灰階或彩圖
    center = (w // 2, h // 2)
    
    # 取得旋轉矩陣
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # 執行仿射轉換 (使用 BORDER_REPLICATE 填補旋轉後的黑邊)
    aligned = cv2.warpAffine(face_img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    
    return aligned

def read_uploaded_image(uploaded_file):
    """將 Django UploadedFile 轉成 OpenCV BGR image"""
    if not isinstance(uploaded_file, (InMemoryUploadedFile, TemporaryUploadedFile)):
        raise InvalidImageError("Uploaded file type is invalid")
    file_bytes = np.frombuffer(uploaded_file.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        raise InvalidImageError("Failed to decode uploaded image")

    return img

# ===================== Main Process =====================

def preprocess_frame(uploaded_file):
    """
    主處理函式
    Return: 
        Success: np.ndarray shape=(1, 224, 224, 1), normalized 0-1
        Fail: None
    """
    # 1. 讀取影像
    frame_bgr = read_uploaded_image(uploaded_file)
    if frame_bgr is None:
        raise InvalidImageError("無法讀取圖片")
    
    h_img, w_img, _ = frame_bgr.shape

    # 2. 臉部偵測 (MediaPipe)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = face_detection.process(frame_rgb)

    if not results.detections:
        raise NoFaceDetectedError("未偵測到臉部")

    # 取信心度最高的一張臉
    # 取信心度最高的一張臉
    detection = results.detections[0]
    bboxC = detection.location_data.relative_bounding_box
    keypoints = detection.location_data.relative_keypoints

    # 3. [新增 Step A] 轉頭檢測
    if not check_head_pose(keypoints, w_img):
        raise NoFaceDetectedError("臉部角度過大 (側臉)")
    

    # 4. 計算旋轉角度 (直接用 MediaPipe 的關鍵點，不用 Haar)
    # 這是最穩定的作法，因為是基於整張臉的結構找到的眼睛
    try:
        angle = get_rotation_angle(detection.location_data.relative_keypoints, w_img, h_img)
    except Exception:
        angle = 0 # 計算失敗就不轉

    # 計算 Bounding Box 座標
    x = int(bboxC.xmin * w_img)
    y = int(bboxC.ymin * h_img)
    w = int(bboxC.width * w_img)
    h = int(bboxC.height * h_img)

    # 座標防呆
    x = max(0, x)
    y = max(0, y)
    w = min(w, w_img - x)
    h = min(h, h_img - y)
    
    if w < 30 or h < 30: 
        raise NoFaceDetectedError("臉部過小或邊界框無效")

    # 5. 裁切 (Crop)
    face_crop_bgr = frame_bgr[y:y+h, x:x+w]
    
    # 6. 轉灰階 (Gray) - 配合模型需求
    face_gray = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2GRAY)

    # 7. [新增 Step C] 模糊檢測
    if not check_blurriness(face_gray):
        # print("Info: 影像過於模糊，視為無效數據")
        return None
    
    # 8. 臉部對齊 (Align) - 使用剛剛算好的角度
    aligned = align_face(face_gray, angle)

    # 9. 尺寸正規化 (Resize) - 配合模型輸入 (224x224)
    try:
        resized = cv2.resize(aligned, (IMG_W, IMG_H), interpolation=cv2.INTER_AREA)
    except Exception:
        if not results.detections:
            raise NoFaceDetectedError("No face detected")
        if w < 30 or h < 30:
            raise NoFaceDetectedError("Face too small or bounding box invalid")

        return None

    # 8. 轉換格式 (Reshape & Normalize)
    # 目前 resized 形狀為 (224, 224)
    
    # 轉為 float32 並增加 Channel 維度: (224, 224, 1)
    face_res = resized.astype(np.float32)[..., None]
    
    # 正規化 / 255.0
    face_res = face_res / 255.0
    
    # 增加 Batch 維度 -> (1, 224, 224, 1)
    # 這是 Keras 模型 predict() 必要的格式
    face_final = np.expand_dims(face_res, axis=0)

    return face_final
