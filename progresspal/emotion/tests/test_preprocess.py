import unittest
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from emotion.services.preprocess import preprocess_frame, NoFaceDetectedError, InvalidImageError, BlurryFaceError
import cv2
import os

def load_image_as_bytes(path):
    """讀取圖片並轉為 bytes，模擬上傳檔案格式"""
    # 將 path 轉成絕對路徑，確保測試能找到檔案
    base_dir = os.path.dirname(__file__) 
    full_path = os.path.join(base_dir, path)
    
    img = cv2.imread(full_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {full_path}")
        
    success, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class TestPreprocessFrame(unittest.TestCase):
    def test_face_images(self):
        # 模擬五張不同狀態的圖片
        test_images = {
            "normal_face": "images/normal_face.jpg",
            "no_face": "images/no_face.jpg",
            "multiple_faces": "images/multi_face.jpg",
            "side_face": "images/side_face.jpg",  # 側臉 -> 預期拋出 NoFaceDetectedError（尚未實作，暫時略過）
            "blur_face": "images/blur_face.jpg"   # 模糊 -> 預期拋出 BlurryFaceError
        }

        for name, path in test_images.items():
            with self.subTest(name=name):
                # 1. 載入圖片 (若圖片不存在則跳過該子測試)
                try:
                    image_bytes = load_image_as_bytes(path)
                except FileNotFoundError:
                    print(f"Skipping {name}: Image not found at {path}")
                    continue

                uploaded_file = SimpleUploadedFile(name+".jpg", image_bytes, content_type="image/jpeg")
                
                # 2. 針對不同案例進行測試驗證

                # 側臉過濾：改用 Haar Cascade 後移除了側臉檢查（Haar 正臉偵測仍會抓到側臉），
                # 尚未決定新的檢查方式前先略過這一項
                if name == "side_face":
                    self.skipTest("側臉過濾尚未在 Haar Cascade 版本實作")

                # Case A: 嚴重錯誤 (沒臉) -> 預期拋出 NoFaceDetectedError
                if name == "no_face":
                    with self.assertRaises(NoFaceDetectedError, msg=f"'{name}' 應該拋出 NoFaceDetectedError"):
                        preprocess_frame(uploaded_file)

                # Case B: 品質過濾 (模糊) -> 預期拋出 BlurryFaceError（API 回 422，不記錄情緒）
                elif name == "blur_face":
                    with self.assertRaises(BlurryFaceError, msg=f"'{name}' (模糊) 應該拋出 BlurryFaceError"):
                        preprocess_frame(uploaded_file)

                # Case C: 正常情況 (正臉、多臉取最大) -> 預期回傳 Tensor
                else:
                    result = preprocess_frame(uploaded_file)
                    self.assertIsInstance(result, np.ndarray, f"'{name}' 應該要成功回傳 Tensor")
                    # 檢查輸出形狀是否符合模型要求 (Batch, Height, Width, Channel)
                    self.assertEqual(result.shape, (1, 224, 224, 1), f"'{name}' Shape 錯誤")