from django.contrib import admin
from .models import Chapter, Unit

# Register your models here.
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('chapter_number', 'title')

class UnitAdmin(admin.ModelAdmin):
    list_display = ('chapter','unit_number', 'title' )
    ordering = ('chapter__chapter_number', 'unit_number')
    list_filter = ('chapter',)


admin.site.register(Chapter,ChapterAdmin)
admin.site.register(Unit,UnitAdmin)
