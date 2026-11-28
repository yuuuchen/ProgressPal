from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from learning.models import QuizQuestion 

# 使用者
class CustomUser(AbstractUser):
    """
    自訂使用者模型：
    - 繼承 AbstractUser（內含 username、password）
    - 新增身份與年級欄位
    """
    # ROLE_CHOICES = [
    #     ('high_prior_student', '高先備知識學生'),
    #     ('low_prior_student', '低先備知識學生'),
    # ]
    ROLE_CHOICES = [
    ('high_prior_student', 'A'),
    ('low_prior_student', 'B'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='low_prior_student') #身分
    grade = models.CharField(max_length=10, blank=True, null=True) #年級
    nickname = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.nickname} ({self.role})"
    
    EMOTION_MAP = {
        "frustration":"挫折",
        "confusion":"困惑",
        "boredom":"無聊",
        "engagement":"投入",
        "surprise":"驚訝",
        "delight":"喜悅",
    }

    @property
    def recent_emotion_history(self):
        """
        取得最近 6 筆情緒（由遠→近）並回傳中文清單
        """
        records = self.emotion_records.order_by('-timestamp')[:6]  # 最新6筆
        if not records.exists():
            return ["None"]
        records = reversed(records)  # 由遠到近
        return [self.EMOTION_MAP.get(rec.emotion, "未知") for rec in records]

    
# 學習紀錄
class LearningRecord(models.Model):
    """
    紀錄使用者每次進入學習單元的起訖時間
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='learning_records')
    chapter_code = models.CharField(max_length=50, blank=True, null=True)  # 章節代碼（例：CH1）
    unit_code = models.CharField(max_length=50, blank=True, null=True)     # 單元代碼（例：CH1-U2）
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(blank=True, null=True)

    @property
    def duration_minutes(self):
        """自動計算學習時長（分鐘）"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return round(delta.total_seconds() / 60, 1)
        return None

    def __str__(self):
        return f"{self.user.username} - {self.unit_code}"
    
# 提問紀錄
class QuestionLog(models.Model): 
    """
    紀錄學生的每次提問與系統回覆
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='question_logs')
    TYPE_CHOICES = [
    ('question', '學生提問'),
    ('answer_extend_question', '學生回應引導提問'),
]

    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='question')
    chapter_code = models.CharField(max_length=50, blank=True, null=True)
    unit_code = models.CharField(max_length=50, blank=True, null=True)
    stu_input = models.TextField() # 學生輸入
    system_question = models.TextField(blank=True, null=True) # 系統引導提問(當學生回應引導提問時會有內容)
    answer = models.TextField(blank=True, null=True) # 系統回覆
    hint_is_used = models.BooleanField(default=False) # 系統提示(當學生點選使用系統提示時會改為True)
    click_time = models.DateTimeField(blank=True, null=True) # 點擊時間
    engagement = models.CharField(max_length=20, blank=True, null=True)  # 參與度，例如：high、low
    fallback_key_used = models.BooleanField(default=False)  # 這次回應是否改用伺服器的備援 Groq key
    response_seconds = models.FloatField(blank=True, null=True)  # AI 產生這次回應花費的秒數（RQ1 系統可行性）
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q by {self.user.username} @ {self.unit_code or 'N/A'}"

# 事件紀錄（實驗分析用）
class EventLog(models.Model):
    """
    記錄受試者在系統中的互動事件，供 RQ1、RQ3 分析（見 docs/SPEC_實驗資料與部署.md R5）
    """
    # 由前端回報的事件（POST /events/ 只接受這些）
    CLIENT_EVENT_TYPES = [
        ('proactive_trigger', '主動介入觸發'),
        ('hint_shown', '提示出現'),
        ('hint_click', '點擊提示'),
        ('form_link_click', '點擊表單連結'),
    ]
    # 由後端記錄的事件
    SERVER_EVENT_TYPES = [
        ('unit_enter', '進入單元'),
        ('unit_leave', '離開單元'),
        ('extended_q_shown', '延伸提問出現'),
        ('extended_q_answered', '回應延伸提問'),
        ('face_fail', '情緒辨識失敗'),
        ('fallback_key', '使用伺服器備援 key'),
    ]
    EVENT_TYPE_CHOICES = CLIENT_EVENT_TYPES + SERVER_EVENT_TYPES

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='event_logs')
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    chapter_code = models.CharField(max_length=50, blank=True, null=True)
    unit_code = models.CharField(max_length=50, blank=True, null=True)
    question_log = models.ForeignKey(QuestionLog, on_delete=models.SET_NULL, blank=True, null=True,
                                     related_name='events')  # 相關的提問紀錄
    detail = models.JSONField(default=dict, blank=True)  # 補充資訊，例如觸發當下的 low_streak、失敗原因
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} {self.event_type} @ {self.created_at:%H:%M:%S}"


def log_event(user, event_type, chapter_code=None, unit_code=None, question_log=None, detail=None, **extra):
    """寫入一筆事件；chapter_code、unit_code 一律存成字串，detail 與其他關鍵字參數合併存入 detail"""
    def _code(value):
        return None if value in (None, "") else str(value)[:50]
    return EventLog.objects.create(
        user=user,
        event_type=event_type,
        chapter_code=_code(chapter_code),
        unit_code=_code(unit_code),
        question_log=question_log,
        detail={**(detail or {}), **extra},
    )


# 測驗結果
class QuizResult(models.Model):
    """
    儲存每次測驗結果（一次作答）
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='quiz_results'
    )

    chapter_code = models.CharField(max_length=50, blank=True, null=True)
    score = models.IntegerField()  # 0~10 題得分
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.user.username} - {self.chapter_code or 'N/A'}: {self.score}分"

class QuizResultQuestion(models.Model):
    """
    紀錄一次測驗中，每一題的作答狀況
    """
    quiz_result = models.ForeignKey(
        'QuizResult',
        on_delete=models.CASCADE,
        related_name='result_questions',
        verbose_name="所屬測驗結果"
    )

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        verbose_name="題目"
    )

    selected_answer = models.CharField(
        max_length=1,
        choices=QuizQuestion.ANSWER_CHOICES,
        verbose_name="學生作答"
    )

    is_correct = models.BooleanField(verbose_name="是否正確")

    def __str__(self):
        return f"{self.quiz_result.user.username} - Q{self.question.id} - {self.selected_answer}"