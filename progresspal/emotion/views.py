# emotion/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .emotion_model import predict_emotion
from services.preprocess import preprocess_frame  
from .models import EmotionRecord


@login_required
def detect_emotion(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"error": "No image provided"}, status=400)

    # 1. 前處理
    # frame = preprocess_frame(image_file)

    # if frame is None:
    #     return JsonResponse({"error": "Face not detected"}, status=422)

    try:
        frame = preprocess_frame(image_file)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=422)
    except Exception:
        return JsonResponse({"error": "Failed to preprocess image"}, status=400)

    if frame is None:
        return JsonResponse({"error": "Face not detected"}, status=422)

    # 2. 模型推論
    try:
        result = predict_emotion(frame)
        # result = {"emotion": "...", "confidence": 0.92}
    except FileNotFoundError:
        return JsonResponse({"error": "Model not found"}, status=500)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)

    # 3. 存進資料庫
    EmotionRecord.objects.create(
        user=request.user,
        emotion=result["emotion"],
        confidence=result["confidence"]
    )
    return JsonResponse(result)