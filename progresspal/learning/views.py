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

selected_extended_q = None
extended_questions = request.session.get("extended_questions", [])

def homepage(request):
    """學習首頁"""
    chapters = Chapter.objects.prefetch_related('units').all()
    return render(request, "index.html")


def lesson(request):
    """課程總覽頁面"""
    chapters = Chapter.objects.prefetch_related('units').all()
    return render(request, 'learning/lesson.html', {'chapters': chapters})

"""生成教材內容頁面"""
@csrf_exempt
@login_required(login_url='login')
def generate_materials_view(request, chapter_code, unit_code):   
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
    # 將延伸提問拆成陣列
    extended_text = result.get("extended_question") 
    if extended_text:
        question_list = utils.split_extended_questions(extended_text)
        if not question_list:
            question_list = [extended_text]
        # 用 session 保存最新延伸提問
        request.session["extended_questions"] = question_list
        # 確保 session 有變更
        request.session.modified = True
        extended_questions = question_list
    teaching = utils.to_markdown(result.get("teaching"))
    example = utils.to_markdown(result.get("example"))
    summary = utils.to_markdown(result.get("summary"))
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

"""教材問答 """
@csrf_exempt
@login_required(login_url='login')
def answer_question_view(request, chapter_code, unit_code):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    # 取得前端傳來的資料
    question_choice = data.get("question_choice", "direct")
    user_question = data.get("user_question", "")
    selected_index = data.get("selected_question_index", None)
    user = request.user
    role = user.role
    # 計算 engagement（目前寫死）
    emotions = ["喜悅", "投入", "無聊", "挫折", "投入", "投入"]
    engagement = compute_engagement(emotions)
    # ---------- Session 讀取延伸提問 ----------
    extended_questions = request.session.get("extended_questions", [])
    if selected_index is not None:
        try:
            extended_question = extended_questions[selected_index]
        except (IndexError, ValueError):
            return JsonResponse({"error": "Invalid extended question index"}, status=400)
    # mode 判斷
    mode = 1 if question_choice == "extended" else 2
    # 呼叫 AI 回答邏輯
    result = main.answer_question(
        mode=mode,
        question=user_question,
        engagement=engagement,
        chapter_id=chapter_code,
        unit_id=unit_code,
        role=role,
        extended_question = extended_question
    )
    answer = utils.to_markdown(result.get("answer", "系統暫時無法回答，請稍後再試。"))
    # ---------- 處理新的延伸提問（拆成陣列） ----------
    new_extended_text = result.get("extended_question") 
    if new_extended_text:
        new_list = utils.split_extended_questions(new_extended_text)
        if not new_list:
            new_list = [new_extended_text]
        # 用 session 保存最新延伸提問
        request.session["extended_questions"] = new_list
        # 確保 session 有變更
        request.session.modified = True
        extended_questions = new_list
    # ---------- 儲存問答記錄 ----------
    QuestionLog.objects.create(
        user=user,
        chapter_code=chapter_code,
        unit_code=unit_code,
        question=user_question,
        answer=answer,
        engagement=engagement,
        created_at=timezone.now(),
    )
    # ---------- 回傳 JSON ----------
    return JsonResponse({
        "answer": answer,
        "extended_questions": extended_questions
    })