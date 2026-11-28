# accounts/views.py
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model, update_session_auth_hash
from django.db.models import Sum, Avg, Count, F
from django.db.models.functions import TruncDate  # 導入日期截斷函式
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from .models import LearningRecord, QuestionLog, QuizResult, QuizResultQuestion, EventLog, log_event
from accounts.models import CustomUser
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, PasswordChangeForm
from .api_key_session import store_api_key
import os
import json
from collections import Counter, defaultdict # 用於關鍵字分析
from learning.services.utils import KeywordAnalyzer # 用於錯題關鍵字分析
from django.http import JsonResponse
from .services.generate_csv import generate_user_csv_reports


User = get_user_model()

# 註冊頁面
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # 受試者的 Groq API Key 只加密存在這次登入的 Session（不寫入資料庫的使用者資料、不寫入 .env）
            store_api_key(request, form.cleaned_data['api_key'])
            messages.success(request, '註冊成功，已自動登入！')
            return redirect('/lesson/')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

# 登入頁面
def login_view(request):
    next_url = request.GET.get('next')
    if next_url:
        messages.info(request, '請先登入')
        
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            account = form.cleaned_data['account']
            password = form.cleaned_data['password']
            remember = request.POST.get('remember')  # 取得 checkbox 值

            # 嘗試登入
            user = authenticate(request, username=account, password=password)
            if user is None:
                try:
                    user_obj = User.objects.get(email=account)
                    user = authenticate(request, username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

            if user is not None:
                login(request, user)
                store_api_key(request, form.cleaned_data['api_key'])

                # 加入記住我設定
                if remember:
                    # 最長保留 SESSION_COOKIE_AGE（8 小時），之後 Session 與其中的 API Key 一併失效
                    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
                else:
                    # 瀏覽器關閉就自動登出
                    request.session.set_expiry(0)

                messages.success(request, '登入成功，歡迎回來！')
                return redirect('/lesson')
            else:
                messages.warning(request, '帳號/Email 或密碼錯誤，請再試一次。')
        else:
            messages.warning(request, '請確認輸入的資料格式正確。')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})

# 前端回報實驗事件（主動介入觸發、提示出現與點擊、表單連結點擊）
@login_required(login_url='login')
def log_client_event(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    event_type = data.get('event_type')
    if event_type not in dict(EventLog.CLIENT_EVENT_TYPES):
        return JsonResponse({'error': 'Unknown event_type'}, status=400)
    detail = data.get('detail') or {}
    if not isinstance(detail, dict) or len(json.dumps(detail)) > 2000:
        return JsonResponse({'error': 'Invalid detail'}, status=400)
    log_event(request.user, event_type, data.get('chapter_code'), data.get('unit_code'), detail=detail)
    return JsonResponse({'status': 'ok'})

# 登出動作
def logout_view(request):
    logout(request)
    return redirect('homepage')

# @login_required 是 Django 提供的裝飾器，用來限制該視圖（view）只能由已登入的使用者訪問。
@login_required(login_url='login')
def profile(request):
    user = request.user

    if request.method == 'POST':
        profile_form = ProfileUpdateForm(request.POST, instance=user)
        password_form = PasswordChangeForm(user, request.POST)

        if 'update_profile' in request.POST:
            if profile_form.is_valid():
                profile_form.save()
                if profile_form.cleaned_data.get('api_key'):
                    store_api_key(request, profile_form.cleaned_data['api_key'])
                messages.success(request, '個人資料已更新。')
                return redirect('profile')

        elif 'change_password' in request.POST:
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, '密碼已更新。')
                return redirect('profile')
            else:
                messages.error(request, '請確認密碼輸入是否正確。')

    else:
        profile_form = ProfileUpdateForm(instance=user)
        password_form = PasswordChangeForm(user)

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })

# 刪除帳號
@login_required(login_url='login')
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "帳號已成功刪除，再見了！")
        return redirect('/user/login')  # 或導向登入頁/login
    else:
        return redirect('/user/profile')

@login_required(login_url='login')
def learning_portfolio(request, username=None):
    if username:
        if not request.user.is_superuser:
            messages.error(request, "您沒有權限查看其他使用者的學習歷程。")
            return redirect('learning-portfolio-self')
        target_user = get_object_or_404(CustomUser, username=username)
    else:
        target_user = request.user

    # 1. 基礎紀錄 (用於表格)
    learning_records = LearningRecord.objects.filter(user=target_user).order_by('-start_time')
    question_logs = QuestionLog.objects.filter(user=target_user).order_by('-created_at')

    # 1. 總學習時數
    # 計算所有紀錄的總時間差 (不分章節)
    total_duration_result = (
        LearningRecord.objects.filter(user=target_user, end_time__isnull=False)
        .aggregate(total=Sum(F('end_time') - F('start_time')))
    )

    # 提取總時間並轉換為小時
    total_duration = total_duration_result['total']

    if total_duration:
        # 將 timedelta 物件轉為秒數後除以 3600，並四捨五入到小數點後第一位
        total_hours = round(total_duration.total_seconds() / 3600, 1)
    else:
        total_hours = 0.0

    # 3. 各章節學習時間 (Bar Chart)
    # 計算每個章節的總學習時數（分鐘）
    chapter_stats = (
        LearningRecord.objects.filter(user=target_user, end_time__isnull=False)
        .values('chapter_code')
        .annotate(total_time=Sum(F('end_time') - F('start_time')))
        .order_by('chapter_code')
    )
    chapter_labels = []
    chapter_times = []
    for entry in chapter_stats:
        chapter_labels.append(f"CH{entry['chapter_code']}" if entry['chapter_code'] else "未知")
        chapter_times.append(round(entry['total_time'].total_seconds() / 60, 1))

    # 4. 提問參與度趨勢 (按「日期」分組，解決 3/11 資料消失問題)
    # 將參與度轉為數值：high=1, low=0，然後計算每天的平均值
    daily_engagement = (
        QuestionLog.objects.filter(user=target_user)
        .annotate(date=TruncDate('created_at')) # 強制轉為日期 YYYY-MM-DD
        .values('date')
        .annotate(
            avg_eng=Avg(F('engagement') == 'high'), # Django 的布林 Avg 會轉為 0~1 比例
            count=Count('id')
        )
        .order_by('date')[:10] # 顯示最近 10 天
    )
    
    # 如果 Avg 邏輯在你的 DB 報錯，可改用手動計算：
    engagement_labels = []
    engagement_values = []
    for entry in daily_engagement:
        # 重新計算比例 (high 的數量 / 總量)
        day_logs = QuestionLog.objects.filter(user=target_user, created_at__date=entry['date'])
        high_count = day_logs.filter(engagement='high').count()
        total_count = day_logs.count()
        
        engagement_labels.append(entry['date'].strftime('%m/%d'))
        engagement_values.append(round(high_count / total_count, 2) if total_count > 0 else 0)

    # 5. 參與度 vs 學習時間 (Scatter Chart)
    scatter_data = []
    for i, ch_code in enumerate([item['chapter_code'] for item in chapter_stats]):
        ch_questions = QuestionLog.objects.filter(user=target_user, chapter_code=ch_code)
        if ch_questions.exists():
            h_count = ch_questions.filter(engagement='high').count()
            avg_eng = h_count / ch_questions.count()
            scatter_data.append({
                'x': chapter_times[i],
                'y': round(avg_eng, 2),
                'label': f"CH{ch_code}"
            })

    context = {
        'target_user': target_user,
        'total_hours': total_hours,
        'learning_records': learning_records,
        'question_logs': question_logs,
        # 必須傳入以下變數，圖表才會有資料
        'chapter_labels': json.dumps(chapter_labels),
        'chapter_times': json.dumps(chapter_times),
        'engagement_labels': json.dumps(engagement_labels),
        'engagement_values': json.dumps(engagement_values),
        'scatter_data': json.dumps(scatter_data),
    }

    return render(request, 'accounts/learning-portfolio.html', context)

@login_required(login_url='login')
def learning_portfolio_quiz(request, username=None):
    # =========================
    # 1️. 基本資料
    # =========================
    if username:
        if not request.user.is_superuser:
            messages.error(request, "您沒有權限查看其他使用者的學習歷程。")
            return redirect('learning-portfolio-quiz-self')
        target_user = get_object_or_404(CustomUser, username=username)
    else:
        target_user = request.user

    learning_records = LearningRecord.objects.filter(user=target_user).order_by('-start_time')
    question_logs = QuestionLog.objects.filter(user=target_user).order_by('-created_at')
    quiz_results = QuizResult.objects.filter(user=target_user).order_by('-created_at')

    # =========================
    # 2. Learning Curve（章節學習曲線）
    # =========================
    chapter_attempts = defaultdict(list)

    quizzes_ordered = QuizResult.objects.filter(user=target_user).order_by('created_at')

    for q in quizzes_ordered:
        ch = q.chapter_code or "未知"
        chapter_attempts[ch].append(q.score)

    learning_curve_data = []

    for ch, scores in chapter_attempts.items():
        learning_curve_data.append({
            "chapter": f"CH{ch}",
            "scores": scores,
            "attempts": list(range(1, len(scores) + 1))
        })

    # =========================
    # 3. 錯題（用於分析與列表）
    # =========================
    # 加上排序 .order_by('quiz_result__chapter_code') 確保 regroup 正常
    wrong_questions = QuizResultQuestion.objects.filter(
        quiz_result__user=target_user,
        is_correct=False
    ).select_related('question', 'quiz_result').order_by('quiz_result__chapter_code', '-quiz_result__created_at')
    # =========================
    # 4. Stacked Bar（章節 × 難度）
    # =========================
    difficulty_map = defaultdict(lambda: {'easy': 0, 'medium': 0, 'hard': 0})

    for wq in wrong_questions:
        ch = wq.quiz_result.chapter_code or "未知"
        diff = wq.question.difficulty
        difficulty_map[ch][diff] += 1

    stacked_bar_labels = []
    easy_data = []
    medium_data = []
    hard_data = []

    for ch, diffs in difficulty_map.items():
        stacked_bar_labels.append(f"CH{ch}")
        easy_data.append(diffs['easy'])
        medium_data.append(diffs['medium'])
        hard_data.append(diffs['hard'])

    # =========================
    # 5. Top 錯題（關鍵字 mapping）
    # =========================

    keyword_counter = Counter()

    for wq in wrong_questions:
        q_text = wq.question.question
        keywords = KeywordAnalyzer.extract_keywords(q_text)  # ← 用 class method

        for kw in keywords:
            keyword_counter[kw] += 1

    top_keywords = keyword_counter.most_common(5)

    top_keyword_labels = [k for k, _ in top_keywords]
    top_keyword_values = [v for _, v in top_keywords]
    top_keywords_combined = list(zip(top_keyword_labels, top_keyword_values))
    # =========================
    # 6. 學習指引（導回章節）
    # =========================
    difficulty_wrong = {'easy': 0, 'medium': 0, 'hard': 0}
    chapter_wrong = Counter()

    for wq in wrong_questions:
        diff = wq.question.difficulty
        ch = wq.quiz_result.chapter_code or "未知"

        difficulty_wrong[diff] += 1
        chapter_wrong[ch] += 1

    guidance_text = ""
    guidance_url = ""
    weakest_chapter = None

    if chapter_wrong:
        weakest_chapter = chapter_wrong.most_common(1)[0][0]

        if difficulty_wrong['easy'] >= max(difficulty_wrong['medium'], difficulty_wrong['hard']):
            guidance_text = f"你在 CH{weakest_chapter} 的基礎題錯誤較多，建議先回到該章節重新閱讀核心概念。"

        elif difficulty_wrong['medium'] >= difficulty_wrong['hard']:
            guidance_text = f"你在 CH{weakest_chapter} 的中等難度題目表現不穩定，建議回到範例題區重新理解解題流程。"

        else:
            guidance_text = f"你在 CH{weakest_chapter} 的進階題目較容易出錯，建議重新完整學習該章節內容並再練習。"

        guidance_url = f"/lesson/{weakest_chapter}/1/study"

    else:
        guidance_text = "目前沒有明顯錯題，請持續學習新的章節！"

    # =========================
    # 7. Context
    # =========================
    context = {
        'target_user': target_user,
        'quiz_results': quiz_results,
        'wrong_questions': wrong_questions,

        # Learning Curve
        'learning_curve_data': json.dumps(learning_curve_data),

        # Stacked Bar
        'stacked_bar_labels': json.dumps(stacked_bar_labels),
        'easy_data': json.dumps(easy_data),
        'medium_data': json.dumps(medium_data),
        'hard_data': json.dumps(hard_data),

        # Top keyword
        'top_keywords_combined': top_keywords_combined,  # 給前端顯示用

        # Guidance
        'guidance_text': guidance_text,
        'guidance_url': guidance_url,
        'weakest_chapter': weakest_chapter,
    }

    return render(request, 'accounts/learning-portfolio-quiz.html', context)

@login_required
def csv_output(request):
    username = request.user.username
    result = generate_user_csv_reports(username, system_type="control")

    if result['status'] == 'success':
        cloud_url = "https://drive.google.com/drive/folders/1u_bDCZYu1Jgfs9bosYRl_cCme89yGeqS?usp=sharing"
        
        # 動態定義要在訊息中顯示的資料夾名稱與位置
        folder_name = f"{username}_data"
        folder_path = result.get('folder', folder_name)
        
        messages.success(
            request, 
            f"<strong>🎉 報表輸出成功！</strong><br>"
            f"系統已在 {folder_path} 生成相關 CSV 檔案。<br>"
            f"<span style='color: red;'>⚠️ 提醒：請記得將整份 {folder_name} 資料夾上傳至雲端硬碟進行備份！</span><br><br>"
            f"<a href='{cloud_url}' target='_blank' class='btn btn-success btn-sm'>👉 點我前往雲端硬碟</a>"
        )
    else:
        # 加入失敗訊息
        messages.error(request, f"<strong>❌ 報表輸出失敗</strong><br>原因：{result.get('message', '未知錯誤')}")
    
    # 重新導向回原本的頁面
    return redirect(request.META.get('HTTP_REFERER', '/'))