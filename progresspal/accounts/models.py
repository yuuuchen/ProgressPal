from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

# 使用者
class CustomUser(AbstractUser):
    """
    自訂使用者模型：
    - 繼承 AbstractUser（內含 username、password）
    - 新增身份與年級欄位
    """
    ROLE_CHOICES = [
        ('mis_student', '資訊管理系大學生'),
        ('normal_student', '非資訊領域大學生'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student') #身分
    grade = models.CharField(max_length=10, blank=True, null=True) #年級
    nickname = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True) 

    def __str__(self):
        return f"{self.nickname} ({self.role})"
    
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
    儲存每次測驗結果
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='quiz_results')
    chapter_code = models.CharField(max_length=50, blank=True, null=True)
    unit_code = models.CharField(max_length=50, blank=True, null=True)
    score = models.IntegerField()  # 每次 0~3 題的得分
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.chapter_code}-{self.unit_code}: {self.score}分"