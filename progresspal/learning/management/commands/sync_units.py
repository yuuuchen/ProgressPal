import csv
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from learning.models import Chapter, Unit

class Command(BaseCommand):
    help = '初始化資料庫：建立章節、單元'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("正在清除舊資料..."))
        Unit.objects.all().delete()    # 先刪除單元（因為外鍵關聯）
        Chapter.objects.all().delete() # 再刪除章節
        
        # 定義完整的教材單元資料
        course_structure = [
            {
                "chapter_num": 1,
                "chapter_title": "堆疊與佇列",
                "units": [
                    (1, "堆疊 (Stack)"),
                    (2, "佇列 (Queue)"),
                ]
            }
        ]

        # --- 第一階段：建立/更新章節與單元 ---
        self.stdout.write("=== 正在初始化章節與單元結構 ===")

        for data in course_structure:
            chapter, ch_created = Chapter.objects.update_or_create(
                chapter_number=data["chapter_num"],
                defaults={'title': data["chapter_title"]}
            )
            ch_status = "建立" if ch_created else "更新"
            self.stdout.write(f"章節 {data['chapter_num']} {ch_status}: {data['chapter_title']}")

            for u_num, u_title in data["units"]:
                unit, u_created = Unit.objects.update_or_create(
                    chapter=chapter,
                    unit_number=str(u_num),
                    defaults={'title': u_title}
                )
                u_status = "建立" if u_created else "更新"
                self.stdout.write(f"  - 單元 {u_num} {u_status}: {u_title}")

        self.stdout.write(self.style.SUCCESS("\n單元同步作業完成！"))
