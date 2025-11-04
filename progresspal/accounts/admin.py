from django.contrib import admin
from .models import CustomUser, LearningRecord, QuestionLog, QuizResult

# 自訂使用者管理
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'nickname', 'email', 'role', 'grade', 'is_active', 'is_staff')
    list_filter = ('role', 'grade', 'is_active', 'is_staff')
    search_fields = ('username', 'nickname', 'email')
    ordering = ('username',)

# 學習紀錄管理
@admin.register(LearningRecord)
class LearningRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter_code', 'unit_code', 'start_time', 'end_time', 'duration_minutes')
    fields = ('user', 'chapter_code', 'unit_code', 'start_time', 'end_time')
    list_filter = ('chapter_code', 'unit_code')
    search_fields = ('user__username',)
    readonly_fields = ('start_time', 'end_time')

# 提問紀錄管理
@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter_code', 'unit_code', 'engagement', 'created_at')
    list_filter = ('engagement', 'chapter_code')
    search_fields = ('user__username', 'question', 'answer')
    readonly_fields = ('created_at',)

# 測驗結果管理
@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter_code', 'unit_code', 'score', 'created_at')
    list_filter = ('chapter_code', 'unit_code')
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)
