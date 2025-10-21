# learning/views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from emotion.services.utils import compute_engagement
from .services import main
from django.utils import timezone
# from .models import Unit, Chapter

from emotion.services.utils import compute_engagement
from .services import main
from .forms import StudyForm
from accounts.models import QuestionLog

# 暫存延伸問題
extended_q_history = {}

def homepage(request):
    # chapters = Chapter.objects.all()
    # units = Unit.objects.all()
    return render(request, "learning/lesson.html",locals())

@csrf_exempt
def study_view(request):
    """整合教材生成與問答頁面"""
    context = {"form": StudyForm()}
    chapter = "1"
    unit = "1"
    emotions = ["喜悅", "困惑", "無聊", "無聊"]  
    engagement = compute_engagement(emotions)

    if request.method == "POST":
        form = StudyForm(request.POST)
        if form.is_valid():
            question_choice = form.cleaned_data["question_choice"]
            user_input = form.cleaned_data["user_input"]
            selected_index = int(form.cleaned_data.get("selected_index", 0))  # 延伸題索引

            # 第一次載入教材
            if (chapter, unit) not in extended_q_history:
                result = main.display_materials(chapter, unit, engagement)
                extended_q_history[(chapter, unit)] = result.get("extended_questions", [])
            else:
                result = {"extended_questions": extended_q_history.get((chapter, unit), [])}

            # 回答延伸問題
            if question_choice == "extended":
                qa_result = main.answer_extended_question(
                    selected_index=selected_index,
                    user_input=user_input,
                    engagement=engagement,
                    chapter_id=chapter,
                    unit_id=unit,
                    extended_q_history=extended_q_history,
                )
                answer = qa_result.get("answer", "")
                extended_q = result["extended_questions"]
            else:
                # 直接提問
                analysis = main.classify_question(user_input)
                if analysis["category"] == "relevant":
                    mode = 2
                elif analysis["category"] == "demand":
                    mode = 3
                else:
                    mode = 0
                if mode in [2, 3]:
                    qa_result = main.answer_question(
                        mode=mode,
                        question=user_input,
                        engagement=engagement,
                        chapter_id=chapter,
                        unit_id=unit,
                        extended_q_history=extended_q_history,
                    )
                    answer = qa_result.get("answer", "")
                else:
                    answer = "這個問題與教材無關"
                extended_q = result["extended_questions"]

            # 儲存問答紀錄
            if request.user.is_authenticated:
                QuestionLog.objects.create(
                    user=request.user,
                    chapter_code=chapter,
                    unit_code=unit,
                    question=user_input,
                    answer=answer,
                    emotion=",".join(emotions),
                    engagement=str(engagement),
                    created_at=timezone.now(),
                )

            context.update({
                "form": form,
                "chapter": chapter,
                "unit": unit,
                "emotions": emotions,
                "engagement": engagement,
                "extended_questions": extended_q,
                "question": user_input,
                "answer": answer,
            })

        else:
            context["form"] = form

    # 結束問答時清空延伸題暫存
    if request.GET.get("end_session") == "1":
        extended_q_history.clear()

    return render(request, "learning/study.html", context)