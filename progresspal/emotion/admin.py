from django.contrib import admin
from .models import EmotionRecord

@admin.register(EmotionRecord)
class EmotionRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'timestamp', 'emotion')
    list_filter = ('timestamp', 'user')
    search_fields = ('user__username',)
    readonly_fields = ('timestamp',)
