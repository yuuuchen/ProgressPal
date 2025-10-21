# learning/views.py
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from emotion.services.utils import compute_engagement
from .services import main
from .forms import StudyForm
from accounts.models import QuestionLog

# 延伸提問暫存結構：{(chapter_code, unit_code): [q1, q2, q3, ...]}
extended_q_history = {}


@login_required
def homepage(request):
    """學習首頁"""
    return render(request, "learning/lesson.html")


@csrf_exempt
@login_required
def generate_materials_view(request, chapter_code, unit_code):
    """
    生成教材內容頁面
    - 接收 URL 傳入的 chapter_code 與 unit_code
    - 接收 emotion app 傳來的 emotions 序列
    """
    if request.method == "POST":
        emotions = request.POST.getlist("emotions", [])
        engagement = compute_engagement(emotions)

        # 呼叫教材生成
        result = main.display_materials(chapter_code, unit_code, engagement)

        # 初始化該單元的延伸問題儲存區
        if (chapter_code, unit_code) not in extended_q_history:
            extended_q_history[(chapter_code, unit_code)] = []

        # 若有生成延伸問題，追加進暫存
        new_qs = result.get("extended_questions")
        if new_qs:
            if isinstance(new_qs, list):
                extended_q_history[(chapter_code, unit_code)].extend(new_qs)
            else:
                extended_q_history[(chapter_code, unit_code)].append(new_qs)

        context = {
            "chapter": chapter_code,
            "unit": unit_code,
            "engagement": engagement,
            "teaching": result.get("teaching"),
            "example": result.get("example"),
            "summary": result.get("summary"),
            "extended_questions": extended_q_history[(chapter_code, unit_code)],
            "form": StudyForm(),
        }
        return render(request, "learning/materials.html", context)

    # GET：初始載入
    return render(request, "learning/materials.html", {"form": StudyForm()})


@csrf_exempt
@login_required
def answer_question_view(request, chapter_code, unit_code):
    """
    教材問答頁面
    - 使用者選擇提問類型與輸入問題
    - 若是延伸提問，傳入最近五個延伸問題
    - 儲存紀錄到 QuestionLog
    """
    if request.method == "POST":
        form = StudyForm(request.POST)
        if form.is_valid():
            question_choice = form.cleaned_data["question_choice"]
            question = form.cleaned_data["user_question"]
            emotions = request.POST.getlist("emotions", [])
            engagement = compute_engagement(emotions)

            # 決定 mode
            if question_choice == "extended":
                mode = 1
                # 取得該單元最近五個延伸問題
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
                extended_q_history={ (chapter_code, unit_code): last_five_qs }  # 傳入最近五題
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

            context = {
                "chapter": chapter_code,
                "unit": unit_code,
                "question": question,
                "answer": answer,
                "engagement": engagement,
                "form": StudyForm(),
                "extended_questions": extended_q_history.get((chapter_code, unit_code), []),
            }
            return render(request, "learning/answer.html", context)

    else:
        form = StudyForm()

    return render(request, "learning/answer.html", {"form": form})