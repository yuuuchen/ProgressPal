# learning/views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from emotion.services.utils import compute_engagement
from .services import main

# 儲存延伸問題紀錄
extended_q_history = {}

@csrf_exempt
def generate_materials_view(request):
    """生成教材內容頁面"""
    if request.method == "POST":
        chapter = request.POST.get("chapter")
        unit = request.POST.get("unit")
        emotions = request.POST.getlist("emotions")  # 假設用表單傳入多個情緒
        engagement = compute_engagement(emotions)

        result = main.display_materials(chapter, unit, engagement)
        extended_q_history[(chapter, unit)] = result.get("extended_question")

        context = {
            "chapter": chapter,
            "unit": unit,
            "engagement": engagement,
            "material": result.get("material"),
            "extended_question": result.get("extended_question"),
        }
        return render(request, "learning/materials.html", context)

    # GET：初始載入
    return render(request, "learning/materials.html")


@csrf_exempt
def answer_question_view(request):
    """教材問答頁面"""
    if request.method == "POST":
        mode = int(request.POST.get("mode", 1))
        question = request.POST.get("question")
        chapter = request.POST.get("chapter")
        unit = request.POST.get("unit")
        emotions = request.POST.getlist("emotions")
        engagement = compute_engagement(emotions)

        result = main.answer_question(mode, question, engagement, chapter, unit, extended_q_history)

        context = {
            "mode": mode,
            "chapter": chapter,
            "unit": unit,
            "question": question,
            "answer": result.get("answer"),
            "engagement": engagement,
        }
        return render(request, "learning/answer.html", context)

    # GET：初始畫面
    return render(request, "learning/answer.html")
