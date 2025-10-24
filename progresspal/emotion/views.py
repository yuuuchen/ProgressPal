# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, F, ExpressionWrapper, DurationField
from django.contrib.auth.decorators import login_required
from .models import LearningRecord, QuestionLog, QuizResult
from datetime import timedelta
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, PasswordChangeForm
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
            return redirect('lessons/')
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
                return redirect('/lessons')
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
    
# 學習歷程
@login_required(login_url='login')
def learning_portfolio(request):
    user = request.user
    # 計算每筆紀錄的學習時間（秒）
    learning_records = LearningRecord.objects.filter(user=user)
    valid_records = learning_records.exclude(end_time__isnull=True)

    # === 各章節累積花費時間 ===
    chapter_stats = (
        valid_records
        .values('chapter_code')
        .annotate(total_seconds=Sum(ExpressionWrapper(F('end_time') - F('start_time'), output_field=DurationField())))
        .order_by('chapter_code')
    )

    # === 各單元累積花費時間 ===
    unit_stats = (
        valid_records
        .values('unit_code')
        .annotate(total_seconds=Sum(ExpressionWrapper(F('end_time') - F('start_time'), output_field=DurationField())))
        .order_by('unit_code')
    )

    # 轉成 Chart.js 可用格式
    chapter_labels = [c['chapter_code'] for c in chapter_stats]
    chapter_values = [round(c['total_seconds'].total_seconds() / 60, 1) for c in chapter_stats]

    unit_labels = [u['unit_code'] for u in unit_stats]
    unit_values = [round(u['total_seconds'].total_seconds() / 60, 1) for u in unit_stats]

    # 提問紀錄
    question_logs = QuestionLog.objects.filter(user=user).order_by('-created_at')

    context = {
    'chapter_labels': json.dumps(chapter_labels),
    'chapter_values': json.dumps(chapter_values),
    'unit_labels': json.dumps(unit_labels),
    'unit_values': json.dumps(unit_values),
}
    return render(request, 'accounts/learning-portfolio.html', context)
