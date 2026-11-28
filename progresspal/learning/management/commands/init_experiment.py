"""
初始化實驗資料庫（Docker 容器每次啟動時執行，只有全新資料庫才會真正動作）。

- 資料庫沒有任何章節時：執行 sync_units 建立「第 1 章 堆疊與佇列」，並匯入堆疊與佇列題庫
- 已有章節時：略過。sync_units 會先刪除所有章節，而題庫與作答紀錄都以 CASCADE 關聯章節，
  因此有資料時絕對不能重跑，否則會刪除實驗資料。

題庫 CSV 仍使用舊的章節編號（堆疊 = 3、佇列 = 4），陣列、鏈結串列不在實驗範圍，
所以只匯入 stack&queue_question.csv，並把第 3、4 章改為第 1 章。
"""
import csv
import os
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from learning.models import Chapter
from learning.services.quiz import import_quiz_from_csv

QUIZ_FILE = "stack&queue_question.csv"
OLD_CHAPTERS_TO_FIRST = {"3", "4"}


class Command(BaseCommand):
    help = "全新資料庫時建立實驗章節並匯入堆疊與佇列題庫；已有資料時略過"

    def handle(self, *args, **options):
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA journal_mode=WAL;")  # 多人同時讀寫時較不易鎖住

        if Chapter.objects.exists():
            self.stdout.write("已有章節資料，略過初始化")
            return

        self.stdout.write("全新資料庫：建立章節、單元並匯入堆疊與佇列題庫")
        call_command("sync_units")

        source = os.path.join(settings.BASE_DIR, "learning", "resources", QUIZ_FILE)
        with open(source, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames, rows = reader.fieldnames, list(reader)
        for row in rows:
            if (row.get("chapter") or "").strip() in OLD_CHAPTERS_TO_FIRST:
                row["chapter"] = "1"

        fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            import_quiz_from_csv(tmp_path)
        finally:
            os.remove(tmp_path)
