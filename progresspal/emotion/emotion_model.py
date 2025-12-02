# emotion/emotion_model.py
import os
import numpy as np
import traceback
import keras 

class InputShapeError(Exception):
    """輸入影像尺寸錯誤"""
    pass

# 模型檔案路徑
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "small_label5_aug_best_model_fold_8_v94.74.keras"
)

EMOTION_LABELS = ["挫折", "困惑", "無聊", "喜悅", "投入", "驚訝"]

# 全域變數
model = None

def load_emotion_model():
    global model
    if model is None:
        try:
            model = keras.models.load_model(MODEL_PATH)
            print("模型載入成功 (Grayscale Mode)")
        except Exception as e:
            print(f"模型載入失敗: {e}")
            raise RuntimeError(f"載入模型時發生錯誤：{str(e)}")

def predict_emotion(face_input: np.ndarray) -> dict:
    load_emotion_model()

    # 1. 基本檢查
    if face_input is None:
        raise InputShapeError("輸入影像為 None")

    # 2. 轉 float32 (注意：preprocess.py 已經做過 /255 正規化，這裡保持原樣)
    x = face_input.astype("float32")

    # 3. 通道檢查:模型需要 (None, 224, 224, 1)，如果輸入意外變成 RGB (..., 3)，則轉回灰階
    if x.shape[-1] == 3:
        print("偵測到 RGB 輸入，正在轉為灰階以符合模型需求...")
        # RGB 轉灰階:numpy 平均
        x = np.mean(x, axis=-1, keepdims=True)

    try:
        # 4. 模型推論
        preds = model.predict(x, verbose=0)
        preds_vector = preds[0] # 取出第一筆

        # 5. 解析結果
        max_idx = np.argmax(preds_vector)
        
        if max_idx < len(EMOTION_LABELS):
            emotion = EMOTION_LABELS[max_idx]
        else:
            emotion = "Unknown"

        confidence = float(preds_vector[max_idx])

        return {
            "emotion": emotion,
            "confidence": confidence
        }

    except Exception as e:
        print(f"推論錯誤: {e}")
        traceback.print_exc()
        raise RuntimeError(f"模型推論失敗: {str(e)}")