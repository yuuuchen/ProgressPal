# emotion/emotion_model.py
import numpy as np
import traceback
from tensorflow.keras.models import load_model
'''
載入 model.
接收預處理後的輸入（np.ndarray）
回傳情緒與confidence score.
'''
MODEL_PATH = "emotion/small_label5_aug_best_model_fold_8_v94.74.keras"

# Emotion label list
EMOTION_LABELS = [ "喜悅", "投入", "驚訝", "無聊", "挫折", "困惑"]

# 載入模型
try:
    model = load_model(MODEL_PATH)
except FileNotFoundError:
    print(f"[ERROR] Emotion model not found: {MODEL_PATH}")
    model = None
except Exception as e:
    print("[ERROR] Failed to load emotion model:", str(e))
    model = None

# 2. Predict Emotion Function
def predict_emotion(face_input: np.ndarray) -> dict:
    """
    Predict emotion from a (224,224,1) ndarray.
    Returns: {"emotion": "...", "confidence": 0.92}
    """
    # model is not loaded
    if model is None:
        raise FileNotFoundError("Emotion model failed to load.")

    # Validate shape
    if face_input is None or face_input.shape != (224, 224, 1):
        raise ValueError(f"InputShapeError: expected (224,224,1), got {face_input.shape}")

    try:
        # Add batch dimension
        x = np.expand_dims(face_input, axis=0)

        # Normalize if needed
        x = x.astype("float32") / 255.0

        # Model inference
        preds = model.predict(x)
        preds = preds[0]  # (7,)

        max_idx = np.argmax(preds)
        emotion = EMOTION_LABELS[max_idx]
        confidence = float(preds[max_idx])

        return {"emotion": emotion, "confidence": confidence}

    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Model inference failed: {str(e)}")
