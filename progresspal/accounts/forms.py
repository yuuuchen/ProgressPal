from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from captcha.fields import CaptchaField

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
    captcha = CaptchaField(label='驗證碼')

    class Meta:
        model = User
        fields = ['username', 'nickname', 'email', 'role', 'grade', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-control'})
        self.fields['captcha'].widget.attrs.update({'class': 'form-control'})

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
        fields = ['nickname', 'email', 'grade']
        widgets = {
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'grade': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nickname': '暱稱',
            'email': '電子郵件',
            'grade': '年級',
        }
