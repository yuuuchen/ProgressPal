from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from .models import CustomUser

User = get_user_model()

# 暱稱格式驗證器
nickname_validator = RegexValidator(
    regex=r'^[\u4e00-\u9fa5a-zA-Z0-9_-]+$',
    message='只能包含中文、英文、數字、底線 _ 和連字號 -'
)

# 註冊表單
class RegisterForm(UserCreationForm):
    username = forms.CharField(
        label='使用者名稱',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': '請輸入使用者名稱'}),
    )
    nickname = forms.CharField(
        label='暱稱',
        max_length=30,
        required=False,
        validators=[nickname_validator],
        widget=forms.TextInput(attrs={'placeholder': '請輸入暱稱'}),
        help_text='只能包含中文、英文、數字、底線 _、連字號 -'
    )
    email = forms.EmailField(
        label='電子郵件',
        widget=forms.EmailInput(attrs={'placeholder': '請輸入 Email'})
    )
    role = forms.ChoiceField(
        label='身分別',
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    grade = forms.CharField(
        label='年級',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '例：大一、大二、大三'}),
    )

    class Meta:
        model = User
        fields = ['username', 'nickname', 'email', 'role', 'grade', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-control'})

# 登入表單
class LoginForm(forms.Form):
    account = forms.CharField(
        label='帳號或 Email',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入帳號或 Email'
        })
    )
    password = forms.CharField(
        label='密碼',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '請輸入密碼'
        })
    )

# 個人資料更新表單
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['nickname', 'email','role', 'grade']
        widgets = {
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nickname': '暱稱',
            'email': '電子郵件',
            'role': '身分別',
            'grade': '年級',
        }

class PasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="舊密碼",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password1 = forms.CharField(
        label="新密碼",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label="確認新密碼",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

# 假資料新增表單
class AddMaterialForm(forms.Form):
    DATA_TYPE_CHOICES = [
        ('learning', '學習紀錄'),
        ('question', '提問紀錄'),
        ('quiz', '測驗結果'),
    ]

    data_type = forms.ChoiceField(choices=DATA_TYPE_CHOICES, label="假資料類型")
    username = forms.ModelChoiceField(
        queryset=CustomUser.objects.all(),
        label="學生帳號 (username)"
    )
    chapter_code = forms.CharField(max_length=50, required=False, label="章節代碼 (例: CH1)")
    unit_code = forms.CharField(max_length=50, required=False, label="單元代碼 (例: CH1-U1)")

    # 學習紀錄專用時間欄位
    start_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label="開始時間"
    )
    end_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label="結束時間"
    )

    # 提問紀錄欄位
    question = forms.CharField(widget=forms.Textarea, required=False, label="提問內容")
    answer = forms.CharField(widget=forms.Textarea, required=False, label="系統回覆")
    engagement = forms.ChoiceField(
        choices=[('high', '高'), ('low', '低')],
        required=False, label="參與度"
    )

    # 測驗紀錄欄位
    score = forms.IntegerField(required=False, min_value=0, max_value=3, label="測驗分數 (0~3)")

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')

        # 驗證必填欄位
        if data_type == 'learning':
            if not cleaned_data.get('start_time'):
                self.add_error('start_time', '學習紀錄需要填寫開始時間')
            if not cleaned_data.get('end_time'):
                self.add_error('end_time', '學習紀錄需要填寫結束時間')
        elif data_type == 'question':
            if not cleaned_data.get('question'):
                self.add_error('question', '提問紀錄需要填寫問題內容')
            if not cleaned_data.get('engagement'):
                self.add_error('engagement', '提問紀錄需要填寫參與度')
        elif data_type == 'quiz':
            if cleaned_data.get('score') is None:
                self.add_error('score', '測驗結果需要填寫分數')

        return cleaned_data