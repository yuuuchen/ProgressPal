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
    ROLE_CHOICES = [
        ('mis_student', '資訊領域大學生'),
        ('normal_student', '非資訊領域大學生'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student') #身分
    grade = models.CharField(max_length=10, blank=True, null=True) #年級
    nickname = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True) 

    def __str__(self):
        return f"{self.nickname} ({self.role})"
    
EMOTION_MAP = {
    "frustrated": "挫折",
    "confused": "困惑",
    "bored": "無聊",
    "engaged": "投入",
    "surprised": "驚訝",
    "happy": "喜悅",
}

@property
def recent_emotion_history(self):
    """
    取得最近 6 筆情緒（由遠→近）並回傳中文清單
    """
    records = self.emotion_records.order_by('-timestamp')[:6]  # 最新6筆
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
        return f"{self.user.username} - {self.unit_name}"
    
# 提問紀錄
class QuestionLog(models.Model):
    """
    紀錄學生的每次提問與系統回覆
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='question_logs')
    chapter_code = models.CharField(max_length=50, blank=True, null=True)
    unit_code = models.CharField(max_length=50, blank=True, null=True)
    question = models.TextField() # 學生提問
    answer = models.TextField(blank=True, null=True) # 系統回覆
    engagement = models.CharField(max_length=20, blank=True, null=True)  # 參與度，例如：high、low
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q by {self.user.username} @ {self.unit_code or 'N/A'}"

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
    unit_code = models.CharField(max_length=50, blank=True, null=True)

    score = models.IntegerField()  # 0~10 題得分

    total_questions = models.PositiveIntegerField(
        verbose_name="題目總數",
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.chapter_code}-{self.unit_code}: {self.score}分"
    

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

    answered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作答時間"
    )

    def __str__(self):
        return f"{self.quiz_result.user.username} - Q{self.question.id} - {self.selected_answer}"