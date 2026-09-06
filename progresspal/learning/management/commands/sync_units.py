import csv
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from learning.models import Chapter, Unit,QuizQuestion

class Command(BaseCommand):
    help = '初始化資料庫：建立章節、單元並匯入測驗題目'

    def handle(self, *args, **options):
        # 定義完整的教材單元資料
        course_structure = [
            {
                "chapter_num": 1,
                "chapter_title": "陣列 (Array)",
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
                "chapter_title": "鏈結串列 (Linked List)",
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
                "chapter_title": "堆疊 (Stack)",
                "units": [
                    (1, "什麼是堆疊"),
                    (2, "堆疊的實作方法(上)"),
                    (3, "堆疊的實作方法(下)"),
                    (4, "堆疊的應用"),
                    (5, "堆疊使用Python實作總結")
                ]
            },
            {
                "chapter_num": 4,
                "chapter_title": "佇列 (Queue)",
                "units": [
                    (1, "佇列簡介"),
                    (2, "佇列的實作方式(上)"),
                    (3, "佇列的實作方式(下)"),
                    (4, "佇列進階概念與應用")
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

        self.stdout.write(self.style.SUCCESS("\n=== 開始匯入測驗題目 ==="))
        self.import_quizzes()
        self.stdout.write(self.style.SUCCESS("\n單元與測驗同步作業完成！"))


    def import_quizzes(self):
        """掃描 resources 資料夾並處理 CSV"""
        resources_dir = os.path.join(settings.BASE_DIR, 'learning', 'resources')
        
        if not os.path.exists(resources_dir):
            self.stdout.write(self.style.WARNING("錯誤: 找不到資源目錄"))
            return

        csv_files = [f for f in os.listdir(resources_dir) if f.endswith('.csv')]
        
        for filename in csv_files:
            file_path = os.path.join(resources_dir, filename)
            self.process_quiz_csv(file_path)

    def process_quiz_csv(self, file_path):
        """讀取 CSV 並更新資料庫"""
        # 偵測編碼
        used_encoding = 'utf-8-sig'
        for enc in ['utf-8-sig', 'utf-8', 'big5', 'cp950']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.readline()
                used_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        with open(file_path, 'r', encoding=used_encoding) as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            
            # 取得 CSV 中所有的章節編號
            target_chapters = set()
            for row in rows:
                c_num = row.get('chapter', '').strip()
                if c_num:
                    target_chapters.add(c_num)

            # 更新策略：先刪除 CSV 中涉及章節的舊題目
            if target_chapters:
                QuizQuestion.objects.filter(chapter__chapter_number__in=target_chapters).delete()
                self.stdout.write(f"  - 清空章節 {', '.join(target_chapters)} 的舊題目以便更新敘述")

            questions_to_create = []
            for row in rows:
                try:
                    chapter_num = int(row['chapter'].strip())
                    chapter_obj = Chapter.objects.get(chapter_number=chapter_num)

                    # 處理說明文字的引號問題
                    raw_explanation = row.get('explanation', '').strip()
                    if raw_explanation.startswith('"') and raw_explanation.endswith('"'):
                        clean_explanation = raw_explanation[1:-1]
                    else:
                        clean_explanation = raw_explanation

                    # 建立題目物件
                    questions_to_create.append(QuizQuestion(
                        chapter=chapter_obj,
                        difficulty=row.get('difficulty', 'easy').strip(),
                        question=row.get('question', '').strip(),
                        option_a=row.get('option_A', '').strip(),
                        option_b=row.get('option_B', '').strip(),
                        option_c=row.get('option_C', '').strip(),
                        option_d=row.get('option_D', '').strip(),
                        answer=row.get('answer', '').strip(),
                        explanation=clean_explanation
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  - 跳過錯誤行: {e}"))

            if questions_to_create:
                QuizQuestion.objects.bulk_create(questions_to_create)
                self.stdout.write(f"  - 檔案 {os.path.basename(file_path)}: 成功匯入 {len(questions_to_create)} 筆題目")