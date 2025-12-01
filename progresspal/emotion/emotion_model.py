# emotion/emotion_model.py
import os
import numpy as np
import traceback
from tensorflow.keras.models import load_model


"""
載入模型模組
- 在 import 時就載入模型
- 接受前處理後的影像輸入 (1,224,224,1)
- 回傳情緒與信心分數
"""

# 自訂例外類型
class InputShapeError(Exception):
    """輸入影像尺寸錯誤"""
    pass

# 模型檔案路徑
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "small_label5_aug_best_model_fold_8_v94.74.keras"
)

# 情緒標籤
EMOTION_LABELS = ["喜悅", "投入", "驚訝", "無聊", "挫折", "困惑"]

# 載入模型
try:
    model = load_model(MODEL_PATH)
except FileNotFoundError:
    print(f"[ERROR] 找不到情緒模型檔案：{MODEL_PATH}")
    model = None
except Exception as e:
    print("[ERROR] 載入情緒模型時發生錯誤：", str(e))
    model = None

# Emotion 預測函式
def predict_emotion(face_input: np.ndarray) -> dict:
    """
    使用已載入的模型進行情緒預測。
    參數：
        face_input: np.ndarray, shape 必須為 (1,224,224,1)
    回傳：
        {"emotion": <str>, "confidence": <float>}
    """

    # 1. 模型未正確載入
    if model is None:
        raise FileNotFoundError("情緒模型載入失敗，無法進行預測。")

    # 2. 輸入 shape 驗證
    expected_shape = (1, 224, 224, 1)
    if face_input is None or face_input.shape != expected_shape:
        raise InputShapeError(
            f"輸入影像尺寸錯誤：預期 {expected_shape}，實際為 {face_input.shape}"
        )

    try:
        # 3. 正規化影像
        x = face_input.astype("float32") / 255.0  # shape 維持 (1,224,224,1)

        # 4. 模型推論
        preds = model.predict(x)
        preds = preds[0]  # shape=(num_classes,)

        # 5. 找出最大機率情緒
        max_idx = np.argmax(preds)
        emotion = EMOTION_LABELS[max_idx]
        confidence = float(preds[max_idx])

        return {
            "emotion": emotion,
            "confidence": confidence
        }

    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"模型推論時發生錯誤：{str(e)}")
