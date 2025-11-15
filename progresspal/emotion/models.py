from django.db import models
from django.conf import settings
from django.utils import timezone
# Create your models here.

class EmotionRecord(models.Model):
    """
    單次影像辨識紀錄（對應一次 webcam snapshot）
    """
    EMOTION_CHOICES = [
    ("frustrated", "挫折"),
    ("confused", "困惑"),
    ("bored", "無聊"),
    ("engaged", "投入"),
    ("surprised", "驚訝"),
    ("happy", "喜悅"),
]


    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="emotion_records"
    )
    emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES)
    confidence = models.FloatField(default=0.0)  # 模型信心分數
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.emotion} ({self.confidence:.2f})"

