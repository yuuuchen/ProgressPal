# emotion/emotion_model.py
import numpy as np
import traceback
from tensorflow.keras.models import load_model

'''
載入模型的模組。
接受已完成前處理的輸入影像（np.ndarray），
並回傳對應的情緒分類與信心分數。
'''

MODEL_PATH = "emotion/small_label5_aug_best_model_fold_8_v94.74.keras"

# 情緒標籤列表
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


# 2. Emotion 預測函式
def predict_emotion(face_input: np.ndarray) -> dict:
    """
    使用已載入之模型，對輸入影像 (224,224,1) 進行情緒預測。
    回傳格式：
        {"emotion": "情緒名稱", "confidence": 0.92}
    """

    # 若模型尚未正確載入，則拋出錯誤
    if model is None:
        raise FileNotFoundError("情緒模型載入失敗。")

    # 驗證輸入影像大小是否符合預期
    if face_input is None or face_input.shape != (224, 224, 1):
        raise ValueError(f"輸入影像尺寸錯誤：預期 (224,224,1)，實際為 {face_input.shape}")

    try:
        # 增加 batch 維度，使形狀變為 (1, 224, 224, 1)
        x = np.expand_dims(face_input, axis=0)

        # 正規化至 [0,1]
        x = x.astype("float32") / 255.0

        # 模型推論
        preds = model.predict(x)
        preds = preds[0]  # 取出第一筆結果，大小為 (N,)

        # 取得最大機率之情緒索引
        max_idx = np.argmax(preds)
        emotion = EMOTION_LABELS[max_idx]
        confidence = float(preds[max_idx])

        return {"emotion": emotion, "confidence": confidence}

    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"模型推論時發生錯誤：{str(e)}")