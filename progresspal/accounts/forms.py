import secrets

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from .models import CustomUser
from .groq_keys import validate_groq_api_key

User = get_user_model()

def _clean_groq_api_key(value):
    """去除空白並向 Groq 驗證；空值直接回傳（是否必填由欄位決定）"""
    value = (value or '').strip()
    if value:
        error = validate_groq_api_key(value)
        if error:
            raise forms.ValidationError(error)
    return value


# 暱稱格式驗證器
nickname_validator = RegexValidator(
    regex=r'^[\u4e00-\u9fa5a-zA-Z0-9_-]+$',
    message='只能包含中文、英文、數字、底線 _ 和連字號 -'
)

def _api_key_field(required=True, label='Groq API Key',
                   placeholder='請貼上您的 Groq API Key（gsk_ 開頭）'):
    return forms.CharField(
        label=label,
        required=required,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': placeholder,
                                          'autocomplete': 'off'}),
    )


# 註冊表單（實驗版：只填受試者編號、組別、API Key；email 與密碼由系統設定）
class RegisterForm(forms.ModelForm):
    username = forms.CharField(
        label='受試者編號',
        max_length=150,
        validators=[User.username_validator],  # 只允許英數字與 @ . + - _（不可有空白）
        widget=forms.TextInput(attrs={'placeholder': '請輸入研究人員發給你的編號'}),
    )
    role = forms.ChoiceField(
        label='組別',
        # label="身分",
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    api_key = _api_key_field()  # 必填：每位受試者以自己的 Key 呼叫 AI 助教，只存在 Session

    class Meta:
        model = User
        fields = ['username', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-control'})

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('這個編號已經註冊過了，請直接登入。')
        return username

    def clean_api_key(self):
        return _clean_groq_api_key(self.cleaned_data.get('api_key'))

    def save(self, commit=True):
        user = super().save(commit=False)
        # email 欄位在資料表中必須唯一，以編號加隨機碼產生（不收集受試者的真實 email）
        user.email = f"{user.username}-{secrets.token_hex(4)}@participant.invalid"
        user.nickname = user.username[:30]
        user.set_password(settings.PARTICIPANT_PASSWORD)
        if commit:
            user.save()
        return user

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
    api_key = _api_key_field()  # 必填：Key 只存在這次登入的 Session，登出或 8 小時後失效

    def clean_api_key(self):
        return _clean_groq_api_key(self.cleaned_data.get('api_key'))

# 個人資料更新表單
class ProfileUpdateForm(forms.ModelForm):
    # 不屬於資料表：有填寫時由 view 更新到 Session
    api_key = _api_key_field(required=False, label='Groq API Key（留空表示不變更）',
                             placeholder='若要更換，請貼上新的 Groq API Key')

    def clean_api_key(self):
        return _clean_groq_api_key(self.cleaned_data.get('api_key'))

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
            # 'role':"身分",
            'role': '組別',
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