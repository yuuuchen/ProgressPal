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
    """
    學習歷程頁面：
    - 若未傳入 username → 顯示自己的學習歷程。
    - 若傳入 username → 僅 superuser 可查看他人。
    """
    # 判斷目標使用者
    if username:
        # 若不是 superuser 則拒絕存取他人資料
        if not request.user.is_superuser:
            messages.error(request, "您沒有權限查看其他使用者的學習歷程。")
            return redirect('learning-portfolio-self')
        target_user = get_object_or_404(CustomUser, username=username)
    else:
        target_user = request.user

    # 取得該使用者的紀錄
    learning_records = LearningRecord.objects.filter(user=target_user).order_by('-start_time')
    question_logs = QuestionLog.objects.filter(user=target_user).order_by('-created_at')
    quiz_results = QuizResult.objects.filter(user=target_user).order_by('-created_at')

    # 統計章節與單元學習時間
    chapter_data = (
        learning_records.values('chapter_code')
        .annotate(total_time=Sum('end_time') - Sum('start_time'))
    )

    context = {
        'target_user': target_user,
        'learning_records': learning_records,
        'question_logs': question_logs,
        'quiz_results': quiz_results,
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