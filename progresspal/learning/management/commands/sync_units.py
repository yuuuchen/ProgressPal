from django.core.management.base import BaseCommand
from learning.models import Chapter, Unit

class Command(BaseCommand):
    help = '根據教材編排圖片同步單元資料庫'

    def handle(self, *args, **options):
        # 定義完整的教材單元資料
        course_structure = [
            {
                "chapter_num": 1,
                "units": [
                    (1, "陣列概論"),
                    (2, "陣列的宣告與初始化"),
                    (3, "陣列的存取與操作"),
                    (4, "陣列的記憶體結構"),
                    (5, "陣列類型介紹"),
                    (6, "Python 陣列與 NumPy 多維陣列實作"),
                    (7, "陣列的時間複雜度與效能分析"),
                    (8, "陣列的優缺點")
                ]
            },
            {
                "chapter_num": 2,
                "units": [
                    (1, "什麼是鏈結串列"),
                    (2, "鏈結串列的常用操作(上)"),
                    (3, "鏈結串列的常用操作(中)"),
                    (4, "鏈結串列的常用操作(下)"),
                    (5, "鏈結串列的類型(上)"),
                    (6, "鏈結串列的類型(下)"),
                    (7, "鏈結串列與陣列的比較(上)"),
                    (8, "鏈結串列與陣列的比較(下)"),
                    (9, "鏈結串列的優缺點"),
                    (10, "鏈結串列的典型應用")
                ]
            },
            {
                "chapter_num": 3,
                "units": [
                    (1, "什麼是堆疊 (Stack)"),
                    (2, "堆疊的實作方法(上)"),
                    (3, "堆疊的實作方法(下)"),
                    (4, "堆疊的應用"),
                    (5, "堆疊使用Python實作總結")
                ]
            },
            {
                "chapter_num": 4,
                "units": [
                    (1, "佇列簡介"),
                    (2, "佇列的實作方式(上)"),
                    (3, "佇列的實作方式(下)"),
                    (4, "佇列進階概念與應用")
                ]
            }
        ]

        self.stdout.write("正在同步單元資料...")

        for data in course_structure:
            try:
                # 根據章節編號抓取現有的章節物件
                chapter = Chapter.objects.get(chapter_number=data["chapter_num"])
                
                for u_num, u_title in data["units"]:
                    # 更新或建立單元
                    # 注意：models.py 中 unit_number 是 CharField
                    unit, created = Unit.objects.update_or_create(
                        chapter=chapter,
                        unit_number=u_num,
                        defaults={'title': u_title}
                    )
                    
                    status = "建立" if created else "更新"
                    self.stdout.write(f"  - 章節 {data['chapter_num']} 單元 {u_num} {status}: {u_title}")
                    
            except Chapter.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"錯誤：找不到章節編號 {data['chapter_num']}，請先確保章節已建立。"))

        self.stdout.write(self.style.SUCCESS("\n單元同步作業完成！"))