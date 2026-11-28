from django.db import models
from django.conf import settings
from django.utils import timezone
# Create your models here.

class EmotionRecord(models.Model):
    """
    單次影像辨識紀錄（對應一次 webcam snapshot）
    """
    EMOTION_CHOICES = [
    ("frustration", "挫折"),
    ("confusion", "困惑"),
    ("boredom", "無聊"),
    ("engagement", "投入"),
    ("surprise", "驚訝"),
    ("delight", "喜悅"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="emotion_records"
    )
    emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES)
    confidence = models.FloatField(default=0.0)  # 模型信心分數
    # 以下由 emotion.services.utils.update_engagement_state 計算（見 docs/SPEC_實驗資料與部署.md R6）
    low_confidence = models.BooleanField(default=False)  # 信心度低於門檻，不列入參與度計算
    engagement = models.CharField(max_length=10, blank=True, null=True)  # 當下參與度 high／low（低信心樣本為空）
    low_streak = models.IntegerField(default=0)  # 目前連續低參與的有效樣本數
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.emotion} ({self.confidence:.2f})"

