# emotion/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .emotion_model import predict_emotion, InputShapeError
from .services.preprocess import preprocess_frame, NoFaceDetectedError, InvalidImageError 
from .models import EmotionRecord


@login_required
def detect_emotion(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)
    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"error": "No image provided"}, status=400)
    
    # 1. Preprocess (含例外處理)
    try:
        frame = preprocess_frame(image_file)
    except NoFaceDetectedError as e:
        # 預期錯誤：臉不明顯、無臉、多臉、模糊
        return JsonResponse({"error": str(e)}, status=421)

    except InvalidImageError as e:
        # 非法圖片格式
        return JsonResponse({"error": str(e)}, status=422)

    except Exception as e:
        # 預防預處理未知錯誤導致系統 crash
        print(f"Unexpected preprocessing error: {e}")
        return JsonResponse({"error": "Failed to preprocess image"}, status=420)

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
        return JsonResponse({"error": str(e)}, status=502)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=502)
    except Exception as e:
        print(f"Unexpected inference error: {e}")
        return JsonResponse({"error": "Failed to perform emotion detection"}, status=500)
    '''
    # 3. 存進資料庫
    EmotionRecord.objects.create(
        user=request.user,
        emotion=result["emotion"],
        confidence=result["confidence"]
    )
    '''
    return JsonResponse(result)