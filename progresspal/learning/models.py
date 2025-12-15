from django.db import models
import random
# Create your models here.
class Chapter(models.Model):
    chapter_number = models.PositiveIntegerField(unique=True, verbose_name="章節數字")
    title = models.CharField(max_length=50, verbose_name="章節標題")

    class Meta:
        ordering = ['chapter_number'] #依照章節數字排序

    def __str__(self):
        return f"{self.chapter_number}. {self.title}"
    def get_units(self):
        """取得該章節所有單元"""
        return self.units.all().order_by('unit_number')
    def get_questions(self):
        """取得該章節所有測驗題目"""
        return self.questions.order_by('difficulty')
    

    
class Unit(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='units', verbose_name="所屬章節")
    unit_number = models.CharField(max_length=10, verbose_name="單元編號") 
    title = models.CharField(max_length=50, verbose_name="單元標題")

    class Meta:
        unique_together = ('chapter', 'unit_number') #確保在同一個章節內的單元編號是唯一的
        ordering = ['unit_number'] #依照單元數字排序

    def __str__(self):
        return f"{self.unit_number} {self.title}"
    

class QuizQuestion(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', '簡單'),
        ('medium', '中等'),
        ('hard', '困難'),
    ]
    
    ANSWER_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ]

    # 關聯到 Chapter，當章節被刪除時，底下的題目也會被刪除 (CASCADE)
    chapter = models.ForeignKey(
        Chapter, 
        on_delete=models.CASCADE, 
        related_name='questions', 
        verbose_name="所屬章節"
    )
    
    difficulty = models.CharField(
        max_length=10, 
        choices=DIFFICULTY_CHOICES, 
        verbose_name="難度"
    )
    
    question = models.TextField(verbose_name="題目內容")
    
    # 使用 TextField 以容納較長的描述或 Markdown
    option_a = models.TextField(verbose_name="選項 A")
    option_b = models.TextField(verbose_name="選項 B")
    option_c = models.TextField(verbose_name="選項 C")
    option_d = models.TextField(verbose_name="選項 D")
    
    answer = models.CharField(
        max_length=1, 
        choices=ANSWER_CHOICES, 
        verbose_name="正確答案"
    )
    
    explanation = models.TextField(verbose_name="解析")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        verbose_name = "測驗題目"
        verbose_name_plural = "測驗題目"

    def __str__(self):
        return f"[{self.chapter.chapter_number}-{self.difficulty}] {self.question[:20]}..."