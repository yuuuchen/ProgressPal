# emotion/services/preprocess.py
'''
影片與圖片的預處理：讀入 → 擷取臉部 → 灰階化 → 對齊 → resize → normalization
'''
import cv2
import math
import numpy as np
from PIL import Image
import os

# 模型輸入大小
IMG_W, IMG_H = 224, 224

# 載入 Haar 分類器（臉與眼）
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")


def preprocess_frame(frame_bgr):
    """
    對單一影格執行預處理：
    1. 轉灰階
    2. 偵測臉部（取最大臉）
    3. 臉部對齊
    4. resize + normalization
    回傳 (ok, face_tensor)
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return False, None

    # 取最大臉
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    roi = gray[y:y+h, x:x+w]
    aligned = _align_by_eyes(roi)
    resized = cv2.resize(aligned, (IMG_W, IMG_H), interpolation=cv2.INTER_AREA)

    # Normalization → (0~1)，shape=(H,W,1)
    face_tensor = resized.astype(np.float32)[..., None] / 255.0
    return True, face_tensor


def preprocess_image(image_path):
    """
    對靜態圖片執行完整預處理，回傳 (ok, face_tensor)
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"找不到圖片檔案: {image_path}")
    return preprocess_frame(img)


def preprocess_video(video_path, frames_per_sec=1):
    """
    對影片進行逐影格擷取與預處理。
    回傳所有處理成功的影格陣列 (X)，shape=(N,224,224,1)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError("無法開啟影片")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total / fps
    timestamps = [t for t in np.arange(0, duration, 1.0 / frames_per_sec)]

    faces = []
    for t in timestamps:
        idx = min(int(round(t * fps)), total - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        ok2, face_tensor = preprocess_frame(frame)
        if ok2:
            faces.append(face_tensor)
    cap.release()

    if len(faces) == 0:
        print("⚠️ 未偵測到任何臉部。")
    return np.stack(faces, axis=0) if faces else np.empty((0, IMG_H, IMG_W, 1), np.float32)


def _align_by_eyes(face_gray):
    """
    嘗試根據眼睛位置對齊臉部，若無法偵測到眼睛則返回原圖。
    """
    h, w = face_gray.shape
    eyes = EYE_CASCADE.detectMultiScale(face_gray, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15))
    if len(eyes) < 2:
        return face_gray

    # 挑選兩顆最上方眼睛，排序確定左右
    eyes = sorted(eyes, key=lambda b: b[1])[:2]
    (x1, y1, w1, h1), (x2, y2, w2, h2) = sorted(eyes, key=lambda b: b[0])
    lc, rc = (x1 + w1 // 2, y1 + h1 // 2), (x2 + w2 // 2, y2 + h2 // 2)

    dy, dx = rc[1] - lc[1], rc[0] - lc[0]
    angle = math.degrees(math.atan2(dy, dx))
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(face_gray, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)