# learning/forms.py
from django import forms

class StudyForm(forms.Form):
    QUESTION_CHOICES = [
        ('direct', '直接提問'),
        ('extended', '延伸提問'),
    ]

    question_choice = forms.ChoiceField(
        label="提問方式",
        choices=QUESTION_CHOICES,
        widget=forms.RadioSelect
    )
    user_question = forms.CharField(
        label="你的問題",
        max_length=500,
        required=True,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "請輸入你的問題..."
        })
    )
