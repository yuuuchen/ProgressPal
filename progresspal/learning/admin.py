from django.contrib import admin
from .models import Chapter, Unit

# Register your models here.
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('chapter_number', 'title')

class UnitAdmin(admin.ModelAdmin):
    list_display = ('chapter','unit_number', 'title' )

admin.site.register(Chapter,ChapterAdmin)
admin.site.register(Unit,UnitAdmin)
