# emotion/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .emotion_model import predict_emotion, InputShapeError
from .services.preprocess import preprocess_frame, NoFaceDetectedError, InvalidImageError 
from .services.utils import compute_engagement, current_engagement, update_engagement_state
from .models import EmotionRecord
from accounts.models import log_event
import logging

logger = logging.getLogger(__name__)


def _log_face_fail(user, reason, message):
    try:
        log_event(user, "face_fail", reason=reason, message=message[:200])
    except Exception as e:
        print(f"face_fail log error: {e}")

REVERSE_EMOTION_CHOICES = {
    "frustration": "挫折",
    "confusion": "困惑",
    "boredom": "無聊",
    "engagement": "投入",
    "surprise": "驚訝",
    "delight": "喜悅",
}

@login_required
def detect_emotion(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"error": "No image provided"}, status=400)
    
    # 1. Preprocess (含例外處理)
    try:
        frame = preprocess_frame(image_file)
    except NoFaceDetectedError as e:
        # 預期錯誤：臉不明顯、無臉、多臉、模糊（記錄下來以計算有效樣本比例）
        _log_face_fail(request.user, "no_face", str(e))
        return JsonResponse({"error": str(e)}, status=422)

    except InvalidImageError as e:
        # 非法圖片格式
        _log_face_fail(request.user, "invalid_image", str(e))
        return JsonResponse({"error": str(e)}, status=422)

    except Exception as e:
        # 預防預處理未知錯誤導致系統 crash
        print(f"Unexpected preprocessing error: {e}")
        return JsonResponse({"error": "Failed to preprocess image"}, status=500)

    # 2. 模型推論
    try:
        result = predict_emotion(frame)
        # result = {"emotion": "...", "confidence": 0.92}
    except FileNotFoundError:
        return JsonResponse({"error": "Model not found"}, status=500)
    except InputShapeError as e:
        print(f"Input shape error: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=500)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        print(f"Unexpected inference error: {e}")
        return JsonResponse({"error": "Failed to perform emotion detection"}, status=500)
    # 3. 存進資料庫
    try:
        EMOTION_CHOICES = {
            "挫折": "frustration",
            "困惑": "confusion",
            "無聊": "boredom",
            "投入": "engagement",
            "驚訝": "surprise",
            "喜悅": "delight",
        }
        record = EmotionRecord.objects.create(
            user=request.user,
            emotion=EMOTION_CHOICES[result["emotion"]],
            confidence=result["confidence"]
        )
    except Exception as e:
        print(f"Database save error: {e}")
        record = None

    # 4. 參與度計算（統一由 update_engagement_state 計算並存入紀錄；前端以 low_streak 判斷主動介入）
    try:
        if record is not None:
            update_engagement_state(record)
            result["low_confidence"] = record.low_confidence
            result["low_streak"] = record.low_streak
        # 低信心樣本沒有自己的參與度，回傳目前（最近一筆有效樣本）的參與度
        result["engagement"] = (record.engagement if record is not None and record.engagement
                                else current_engagement(request.user))

    except Exception as e:
        print(f"Engagement calculation error: {e}")
        result["engagement"] = "unknown" # 若出錯則回傳未知

    return JsonResponse(result)