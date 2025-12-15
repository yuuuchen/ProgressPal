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
from accounts.models import QuestionLog, LearningRecord, QuizResult, QuizResultQuestion
from .models import Chapter, Unit, QuizQuestion
import json

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

    # Engagement（目前寫死）
    emotions = ["喜悅", "投入", "無聊", "挫折", "投入", "投入"]
    engagement = compute_engagement(emotions)

    # 呼叫教材生成
    result = main.display_materials(chapter_code, unit_code, engagement, role)

    # 處理延伸提問
    extended_questions = []
    extended_text = result.get("extended_questions") 
    if extended_text:
        question_list = utils.split_extended_questions(extended_text)
        extended_questions = question_list if question_list else [extended_text]
        # 存進 session
        request.session["extended_questions"] = extended_questions
        request.session.modified = True

    teaching = utils.to_markdown(result.get("teaching"))
    example = utils.to_markdown(result.get("example"))
    summary = utils.to_markdown(result.get("summary"))

    '''
    # 建立學習記錄
    record = LearningRecord.objects.create(
        user=request.user,
        chapter_code=chapter_code,
        unit_code=unit_code
    )
    '''
    context = {
        "chapter": chapter,
        "unit": unit,
        "units":units,
        "previous_unit": previous_unit,
        "next_unit": next_unit,
        "role": role,
        "teaching": teaching,
        "example": example,
        "summary": summary,
        "extended_questions": extended_questions,
        "form": StudyForm(),
        #"record_id": record.id,   # 傳給前端用於關聯學習記錄
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
    selected_index = data.get("selected_question_index")
    user = request.user
    role = user.role

    # Engagement（目前寫死）
    emotions = ["喜悅", "投入", "無聊", "挫折", "投入", "投入"]
    engagement = compute_engagement(emotions)

    # 讀取 session 延伸提問
    extended_questions = request.session.get("extended_questions", [])
    extended_question = None

    if selected_index is not None:
        try:
            extended_question = extended_questions[int(selected_index)]
        except (IndexError, ValueError, TypeError):
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
    answer = utils.to_markdown(result.get("answer", "請詢問與資料結構相關的問題。"))
    
    # 處理新的延伸提問
    new_extended_text = result.get("extended_question")
    if new_extended_text:
        new_list = utils.split_extended_questions(new_extended_text)
        new_list = new_list if new_list else [new_extended_text]

        request.session["extended_questions"] = new_list
        request.session.modified = True
        extended_questions = new_list
    
    # 儲存問答記錄
    QuestionLog.objects.create(
        user=user,
        chapter_code=chapter_code,
        unit_code=unit_code,
        question=user_question,
        answer=answer,
        engagement=engagement,
        created_at=timezone.now(),
    )
    # 回傳 JSON
    return JsonResponse({
        "answer": answer,
        "extended_questions": extended_questions
    })


# 結束學習並更新學習記錄
def end_study(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        record_id = data.get("id")

        try:
            record = LearningRecord.objects.get(id=record_id)
            record.end_time = timezone.now()
            record.save()
            return JsonResponse({"status": "ok"})
        except LearningRecord.DoesNotExist:
            return JsonResponse({"status": "error", "msg": "not found"}, status=400)

    return JsonResponse({"status": "error", "msg": "invalid request"}, status=400)

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
            "id": q.id,
            "question": q.question,
            "options": [q.option_a, q.option_b, q.option_c, q.option_d],
        }
        for q in quiz_questions
    ]
    return JsonResponse(serialized, safe=False)

# 章節測驗批改
@csrf_exempt
@login_required(login_url='login')
def check_answers(request, chapter_code):
    chapter = Chapter.objects.get(chapter_number=chapter_code)
    try:
        body_data = json.loads(request.body)
        user_answers_list = body_data.get('answers', [])        
        if not user_answers_list:
             return JsonResponse({'score': 0, 'results': []})
        # 取得所有題目 ID
        question_ids = [item.get('question_id') for item in user_answers_list]
        questions = QuizQuestion.objects.filter(id__in=question_ids)
        question_map = {q.id: q for q in questions}
        results = []
        score = 0
        details_to_create = []
        with transaction.atomic():        
            for item in user_answers_list:
                q_id = item.get('question_id')
                user_selected = item.get('selected_index')
                question_obj = question_map.get(q_id)
                if not question_obj:
                    continue               
                is_correct = (user_selected == question_obj.answer)
                if is_correct:
                    score += 1
                # 準備回傳前端的 JSON
                results.append({
                    "question_id": question_obj.id,
                    "question": question_obj.question,
                    "options": {
                        "A": question_obj.option_a,
                        "B": question_obj.option_b,
                        "C": question_obj.option_c,
                        "D": question_obj.option_d,
                    },
                    "user_answer": user_selected,
                    "correct_answer": question_obj.answer,
                    "answer_explanation": question_obj.explanation,
                    "is_correct": is_correct,
                })
                # 暫存明細資料
                details_to_create.append({
                    "question": question_obj,
                    "user_answer": user_selected,
                    "is_correct": is_correct
                })
            # --- 寫入資料庫 ---            
            # 1. 建立問題紀錄
            quiz_result = QuizResult.objects.create(
            user=request.user,
            chapter_code=chapter, # 使用 CharField
            unit_code=None,
            score=score,
            )
            # 2. 建立每一題的作答紀錄（明細）
            QuizResultQuestion.objects.bulk_create([
                QuizResultQuestion(
                    quiz_result=quiz_result,
                    quiz_question=d['question'],
                    user_answer=d['user_answer'],
                    is_correct=d['is_correct'],
                )
                for d in details_to_create
            ])
        return JsonResponse({
            "score": score,
            "results": results
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)