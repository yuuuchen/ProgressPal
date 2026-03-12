# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Sum, F, ExpressionWrapper, DurationField
from .models import LearningRecord, QuestionLog, QuizResult
from accounts.models import CustomUser
from django.utils import timezone
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, PasswordChangeForm, AddMaterialForm
import json

User = get_user_model()

# 註冊頁面
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
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

                # 加入記住我設定
                if remember:
                    # 2 週內不用重新登入（1209600 秒）
                    request.session.set_expiry(1209600)
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

    # 基礎紀錄
    learning_records = LearningRecord.objects.filter(user=target_user).order_by('-start_time')
    question_logs = QuestionLog.objects.filter(user=target_user).order_by('-created_at')

    # 1. 統計各章節學習時間 (Bar Chart)
    # 我們排除 end_time 為空的紀錄，並計算分鐘數
    chapter_stats = (
        LearningRecord.objects.filter(user=target_user, end_time__isnull=False)
        .values('chapter_code')
        .annotate(total_minutes=Sum(F('end_time') - F('start_time')))
        .order_by('chapter_code')
    )
    
    # 處理 timedelta 轉為分鐘數
    chapter_labels = []
    chapter_times = []
    for entry in chapter_stats:
        chapter_labels.append(f"CH{entry['chapter_code']}" if entry['chapter_code'] else "未知")
        # 將 timedelta 轉為總分鐘數
        total_sec = entry['total_minutes'].total_seconds()
        chapter_times.append(round(total_sec / 60, 1))

    # 2. 測驗成績趨勢 (Line Chart)
    recent_quizzes = QuizResult.objects.filter(user=target_user).order_by('-created_at')[:10][::-1]
    quiz_labels = [q.created_at.strftime('%m/%d') + f" CH({q.chapter_code})" for q in recent_quizzes]
    quiz_scores = [q.score for q in recent_quizzes]

    # 3. 提問參與度趨勢 (Line Chart)
    # 假設你的 engagement 存的是 'high', 'low'，我們需要轉為數值 1, 0 或其他比例
    # 這裡抓最近 10 次提問的參與度
    engagement_map = {'high': 100, 'mid': 60, 'low': 20}
    recent_questions = question_logs[:10][::-1]
    engagement_labels = [q.created_at.strftime('%m/%d') for q in recent_questions]
    engagement_values = [engagement_map.get(q.engagement, 0) for q in recent_questions]

    # 4. 參與度 vs 學習時間 (Scatter Chart)
    # 我們按章節彙整：該章平均參與度 vs 該章總學習時間
    scatter_data = []
    for entry in chapter_stats:
        ch = entry['chapter_code']
        # 該章節平均參與度
        ch_questions = QuestionLog.objects.filter(user=target_user, chapter_code=ch)
        if ch_questions.exists():
            avg_eng = sum(engagement_map.get(q.engagement, 0) for q in ch_questions) / ch_questions.count()
            scatter_data.append({
                'x': chapter_times[chapter_labels.index(f"CH{ch}")], # 學習時間
                'y': round(avg_eng, 1), # 平均參與度
                'label': f"CH{ch}"
            })

    context = {
        'target_user': target_user,
        'learning_records': learning_records,
        'question_logs': question_logs,
        # 各章節時間
        'chapter_labels': json.dumps(chapter_labels),
        'chapter_times': json.dumps(chapter_times),
        # 測驗成績
        'quiz_labels': json.dumps(quiz_labels),
        'quiz_scores': json.dumps(quiz_scores),
        # 參與度趨勢
        'engagement_labels': json.dumps(engagement_labels),
        'engagement_values': json.dumps(engagement_values),
        # 散佈圖數據
        'scatter_data': json.dumps(scatter_data),
    }

    return render(request, 'accounts/learning-portfolio.html', context)


# 新增假資料頁面（僅 superuser 可用）
@user_passes_test(lambda u: u.is_superuser)
def add_material(request):
    """Superuser 新增假資料頁面"""
    if request.method == 'POST':
        form = AddMaterialForm(request.POST)
        if form.is_valid():
            data_type = form.cleaned_data['data_type']
            user = form.cleaned_data['username']
            chapter_code = form.cleaned_data['chapter_code']
            unit_code = form.cleaned_data['unit_code']

            if data_type == 'learning':
                LearningRecord.objects.create(
                    user=user,
                    chapter_code=chapter_code,
                    unit_code=unit_code,
                    start_time=timezone.now(),
                    end_time=timezone.now() + timezone.timedelta(minutes=30),
                )
                messages.success(request, f"成功新增學習紀錄給 {user.username}")

            elif data_type == 'question':
                QuestionLog.objects.create(
                    user=user,
                    chapter_code=chapter_code,
                    unit_code=unit_code,
                    question=form.cleaned_data['question'],
                    answer=form.cleaned_data['answer'],
                    engagement=form.cleaned_data['engagement'],
                )
                messages.success(request, f"成功新增提問紀錄給 {user.username}")

            elif data_type == 'quiz':
                QuizResult.objects.create(
                    user=user,
                    chapter_code=chapter_code,
                    unit_code=unit_code,
                    score=form.cleaned_data['score'],
                )
                messages.success(request, f"成功新增測驗結果給 {user.username}")

            return redirect('add-material')
    else:
        form = AddMaterialForm()

    return render(request, 'accounts/addMaterial.html', {'form': form})