from django.db import models

# Create your models here.
class Chapter(models.Model):
    chapter_number = models.PositiveIntegerField(unique=True, verbose_name="章節數字")
    title = models.CharField(max_length=50, verbose_name="章節標題")

    class Meta:
        ordering = ['chapter_number'] #依照章節數字排序

    def __str__(self):
        return f"{self.chapter_number}. {self.title}"
    
class Unit(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='units', verbose_name="所屬章節")
    unit_number = models.CharField(max_length=10, verbose_name="單元編號") 
    title = models.CharField(max_length=50, verbose_name="單元標題")

    class Meta:
        unique_together = ('chapter', 'unit_number') #確保在同一個章節內的單元編號是唯一的
        ordering = ['unit_number'] #依照單元數字排序

    def __str__(self):
        return f"{self.unit_number} {self.title}"