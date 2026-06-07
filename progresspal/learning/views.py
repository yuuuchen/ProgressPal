# learning/views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from emotion.services.utils import compute_engagement
from .services import main,utils
from .forms import StudyForm
from accounts.models import QuestionLog, LearningRecord
from .models import Chapter, Unit, QuizQuestion
import json
from datetime import timedelta

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
    """生成教材內容頁面"""   
    chapter = Chapter.objects.get(chapter_number=chapter_code)
    unit = Unit.objects.get(chapter=chapter, unit_number=unit_code)
    units = chapter.get_units()

    unit_list = list(units)
    current_index = unit_list.index(unit)
    previous_unit = None
    next_unit = None
    # 找出上一個單元
    if current_index > 0: 
        previous_unit = unit_list[current_index - 1] 
    # 找出下一個單元
    if current_index >= 0 and current_index < len(unit_list) - 1:
        next_unit = unit_list[current_index + 1]

    user = request.user
    role = user.role

    # Engagement
    emotions = user.recent_emotion_history
    engagement = compute_engagement(emotions)

    current_emotion = emotions[-1] if emotions else "偵測中"

    # 呼叫教材生成
    try:
        # 呼叫教材生成
        result = main.display_materials(chapter_code, unit_code, engagement, role)

    except RuntimeError as e:
        # 捕捉 "所有 Groq API Key 的流量都已耗盡" 的錯誤
        if "耗盡" in str(e) or "quota" in str(e).lower():
            # 渲染額度用盡的提示頁面
            return render(request, "learning/quota_exceeded.html")
        else:
            # 如果是其他未知的 RuntimeError，則重新拋出或做其他處理
            raise e
        
    extended_question = result.get("extended_question", "")
    hint = result.get("hint","")
    request.session["current_extended_question"] = extended_question
    # 建立學習記錄(起點)並傳給前端以便後續更新結束時間
    
    record = LearningRecord.objects.create(
        user=request.user,
        chapter_code=chapter_code,
        unit_code=unit_code
    )
    # 除錯點：在終端機印出來看看
    # print(f"DEBUG: 產生的紀錄 ID 為 {record.id}")

    context = {
        "chapter": chapter,
        "unit": unit,
        "units":units,
        "previous_unit": previous_unit,
        "next_unit": next_unit,
        "role": role,
        "guide": result.get("guide"),
        "core": result.get("core"),
        "example": result.get("example"),
        "extended_question": extended_question, 
        "hint":hint,
        "current_emotion": current_emotion,
        "form": StudyForm(),
        "record_id": record.id,   # 傳給前端用於關聯學習記錄
    }
    return render(request, "learning/study.html", context)

@csrf_exempt
@login_required(login_url='login')
def answer_question_view(request, chapter_code, unit_code):
    """教材問答 """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    # 取得前端資料
    question_choice = data.get("question_choice", "direct")
    user_question = data.get("user_question", "")
    hint_is_used = data.get("hint_is_used",False)
    click_time = data.get("click_time",None)
    user = request.user
    role = user.role

    # Engagement
    emotions = user.recent_emotion_history
    engagement = compute_engagement(emotions)

    # 讀取 session 延伸提問
    extended_q = request.session.get("current_extended_question", "")
    request.session.modified = True
    # print(f"[Debug] 從 session 讀取的延伸提問: {extended_q}")
    # 判斷是否為延伸提問
    is_extended = (question_choice == "extended")

    if is_extended:
        log_type = 'answer_extend_question'
    else:
        log_type = 'question'

    # 呼叫 AI 回答邏輯
    result = main.answer_question(
        question=user_question,
        engagement=engagement,
        chapter_id=chapter_code,
        unit_id=unit_code,
        role=role,
        is_extended=is_extended,
        extended_question_text = extended_q,
    )
    answer = result.get("answer", "請詢問與資料結構相關的問題。")
    hint = result.get("hint", "")
    
    # 處理新的延伸提問
    new_extended_question = result.get("extended_question", "")
    request.session["current_extended_question"] = new_extended_question
    request.session.modified = True

    # 儲存問答記錄
    QuestionLog.objects.create(
        user=user,
        chapter_code=chapter_code,
        unit_code=unit_code,
        type=log_type,
        stu_input=user_question,
        system_question=extended_q,
        answer=answer,
        engagement=engagement,
        hint_is_used=hint_is_used,
        click_time=click_time,
    )
    # 回傳 JSON
    return JsonResponse({
        "answer": answer,
        "extended_questions": new_extended_question,
        "hint": hint,
    })


# 結束學習並更新學習記錄
@csrf_exempt
def end_study(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            record_id = data.get("id")
            duration_seconds = data.get("duration_seconds")

            if record_id:
                record = LearningRecord.objects.get(id=record_id, user=request.user)
                
                # 如果有傳秒數，用 start_time + 秒數
                if duration_seconds is not None:
                    record.end_time = record.start_time + timedelta(seconds=int(duration_seconds))
                else:
                    # 沒傳秒數則用當下時間（備援）
                    record.end_time = timezone.now()
                
                record.save()
                return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"status": "error", "msg": str(e)}, status=400)
    return JsonResponse({"status": "error"}, status=405)

# 將chapter、units 渲染到 quiz頁面
def chapter_quiz_view(request, chapter_code):
    chapter = Chapter.objects.get(chapter_number=chapter_code)
    units = chapter.get_units()
    return render(request, "learning/quiz.html", {
        "chapter": chapter,
        "units": units,
    })
# json 回傳測驗問題與選項給前端
def chapter_quiz_api(request, chapter_code):
    chapter = Chapter.objects.get(chapter_number=chapter_code)
    quiz_questions = main.get_exam_questions(chapter)
    serialized = [
        {
            "question_id": q.id,
            "question": q.question,
            "options": [q.option_a,q.option_b,q.option_c, q.option_d],
        }
        for q in quiz_questions
    ]
    return JsonResponse(serialized, safe=False)

# 章節測驗批改
@csrf_exempt
@login_required(login_url='login')
def check_answers(request, chapter_code):
    try:
        # 解析 Request
        body_data = json.loads(request.body)
        user_answers_list = body_data.get('answers', [])        
        score, results = main.process_quiz_submission(request.user, chapter_code, user_answers_list)       

        for item in results:
            # 確保題目被解析 (解決出現 ` 的問題)
            item['question'] = item.get('question', '')
            # 確保詳解也被解析
            item['explanation'] = item.get('explanation', '')
            
        # 回傳 Response
        return JsonResponse({
            "score": score,
            "results": results
        })
    except Exception as e:
        # 錯誤處理
        return JsonResponse({'error': str(e)}, status=500)