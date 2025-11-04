# learning/views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from emotion.services.utils import compute_engagement
from .services import main,utils
from .forms import StudyForm
from accounts.models import QuestionLog
from .models import Chapter, Unit
import json

# 延伸提問暫存結構：{(chapter_code, unit_code): [q1, q2, q3, ...]}
extended_q_history = {}

def homepage(request):
    """學習首頁"""
    chapters = Chapter.objects.prefetch_related('units').all()
    return render(request, "index.html")


def lesson(request):
    """課程總覽頁面"""
    chapters = Chapter.objects.prefetch_related('units').all()
    return render(request, 'learning/lesson.html', {'chapters': chapters})


@csrf_exempt
@login_required(login_url='login')
def generate_materials_view(request, chapter_code, unit_code):
    """
    生成教材內容頁面
    """
    chapter = Chapter.objects.get(chapter_number=chapter_code)
    unit = Unit.objects.get(unit_number=unit_code)
    units = chapter.get_units()
    user = request.user
    role = user.role

    # 從 emotion app 後端取得情緒序列並計算 engagement
    emotions = ["喜悅","投入","無聊","挫折","投入","投入"]   #寫死
    engagement = compute_engagement(emotions)

    # 呼叫教材生成
    result = main.display_materials(chapter_code, unit_code, engagement, role)

    # 初始化延伸問題暫存
    if (chapter_code, unit_code) not in extended_q_history:
        extended_q_history[(chapter_code, unit_code)] = []

    # 若有生成延伸問題則追加
    new_qs = result.get("extended_questions")
    if new_qs:
        if isinstance(new_qs, list):
            extended_q_history[(chapter_code, unit_code)].extend(new_qs)
        else:
            extended_q_history[(chapter_code, unit_code)].append(new_qs)

    teaching = utils.to_markdown(result.get("teaching"))
    example = utils.to_markdown(result.get("example"))
    summary = utils.to_markdown(result.get("summary"))
    extended_questions = utils.to_markdown(result.get("extended_questions"))

    context = {
        "chapter": chapter,
        "unit": unit,
        "units":units,
        "role": role,
        "teaching": teaching,
        "example": example,
        "summary": summary,
        "extended_questions": extended_questions,
        "form": StudyForm(),
    }
    return render(request, "learning/study.html", context)


@csrf_exempt
@login_required(login_url='login')
def answer_question_view(request, chapter_code, unit_code):
    """
    教材問答 - AJAX JSON 回傳版本
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        question_choice = data.get("question_choice", "direct")
        question = data.get("user_question", "")

        user = request.user
        role = user.role

        # 從 emotion app 後端取得情緒序列並計算 engagement
        emotions = ["喜悅","投入","無聊","挫折","投入","投入"]  #寫死  
        engagement = compute_engagement(emotions)

        # 決定 mode
        if question_choice == "extended":
            mode = 1
            extended_qs = extended_q_history.get((chapter_code, unit_code), [])
            last_five_qs = extended_qs[-5:] if len(extended_qs) > 5 else extended_qs
        else:
            mode = 2
            last_five_qs = []

        # 呼叫回答邏輯
        result = main.answer_question(
            mode=mode,
            question=question,
            engagement=engagement,
            chapter_id=chapter_code,
            unit_id=unit_code,
            role=role,
            extended_q_history={(chapter_code, unit_code): last_five_qs}
        )

        answer = result.get("answer", "系統暫時無法回答，請稍後再試。")

        # 若系統有生成新延伸提問，追加進暫存
        new_q = result.get("extended_question")
        if new_q:
            if (chapter_code, unit_code) not in extended_q_history:
                extended_q_history[(chapter_code, unit_code)] = []
            extended_q_history[(chapter_code, unit_code)].append(new_q)

        # 儲存提問紀錄
        QuestionLog.objects.create(
            user=request.user,
            chapter_code=chapter_code,
            unit_code=unit_code,
            question=question,
            answer=answer,
            engagement=engagement,
            created_at=timezone.now(),
        )

        extended_questions = utils.to_markdown(result.get("extended_questions"))
        # JSON 回傳僅系統生成結果
        return JsonResponse({
            "answer": answer,
            "extended_questions": result.get("extended_questions")
        })

    return JsonResponse({"error": "Invalid request"}, status=400)