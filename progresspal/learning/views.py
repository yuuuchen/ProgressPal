# learning/views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from emotion.services.utils import compute_engagement
from .services import main
from django.utils import timezone

from emotion.services.utils import compute_engagement
from .services import main
from .forms import StudyForm
from accounts.models import QuestionLog

# 暫存延伸問題
extended_q_history = {}

@csrf_exempt
def study_view(request):
    """整合教材生成與問答頁面"""
    context = {"form": StudyForm()}

    # 測試階段：由後端先設定章節與情緒
    chapter = "1"
    unit = "1"
    emotions = ["喜悅", "困惑", "無聊", "無聊"]  
    engagement = compute_engagement(emotions)

    if request.method == "POST":
        form = StudyForm(request.POST)
        if form.is_valid():
            question_choice = form.cleaned_data["question_choice"]
            user_question = form.cleaned_data["user_question"]

            # 第一次載入教材內容
            result = main.display_materials(chapter, unit, engagement)
            extended_q_history[(chapter, unit)] = result.get("extended_question")

            # 決定最終問題（直接 or 延伸）
            if question_choice == "extended":
                question = result.get("extended_question") or user_question
            else:
                question = user_question

            # 取得回答
            qa_result = main.answer_question(
                mode=1,
                question=question,
                engagement=engagement,
                chapter=chapter,
                unit=unit,
                extended_q_history=extended_q_history,
            )
            answer = qa_result.get("answer", "")

            # 儲存問答紀錄
            if request.user.is_authenticated:
                QuestionLog.objects.create(
                    user=request.user,
                    chapter_code=chapter,
                    unit_code=unit,
                    question=question,
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
                "material": result.get("material"),
                "extended_question": result.get("extended_question"),
                "question": question,
                "answer": answer,
            })
        else:
            context["form"] = form

    return render(request, "learning/study.html", context)