"""
匯出實驗分析資料（SPEC R7）

  python manage.py export_analysis --sheets            同步到 Google 試算表（ANALYSIS_SHEET_ID／TEXT_SHEET_ID）
  python manage.py export_analysis --excel [路徑]      輸出 Excel（預設 DB_DIR/exports/）
  python manage.py export_analysis --excel --text      Excel 另外輸出一份對話全文

Docker 容器會每 10 分鐘自動執行 --sheets（見 docker-entrypoint.sh）。
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.analysis_export import NUMERIC_TABLES, TEXT_TABLES, build_tables, sync_to_sheets, write_excel


class Command(BaseCommand):
    help = "匯出實驗分析資料到 Google 試算表或 Excel"

    def add_arguments(self, parser):
        parser.add_argument("--sheets", action="store_true", help="同步到 Google 試算表")
        parser.add_argument("--excel", nargs="?", const="", default=None, metavar="PATH",
                            help="輸出 Excel；不給路徑時存到 DB_DIR/exports/")
        parser.add_argument("--text", action="store_true", help="Excel 另外輸出對話全文檔")

    def handle(self, *args, **options):
        if not options["sheets"] and options["excel"] is None:
            raise CommandError("請指定 --sheets 或 --excel")
        tables = build_tables()
        n = len(tables["summary"][1])

        if options["excel"] is not None:
            stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
            group = settings.EXPERIMENT_GROUP
            path = Path(options["excel"]) if options["excel"] else (
                Path(settings.DB_DIR) / "exports" / f"{group}_analysis_{stamp}.xlsx")
            path.parent.mkdir(parents=True, exist_ok=True)
            write_excel(tables, path, NUMERIC_TABLES)
            self.stdout.write(f"已輸出 {path}（{n} 位受試者）")
            if options["text"]:
                text_path = path.with_name(path.stem.replace("_analysis", "") + "_text.xlsx")
                write_excel(tables, text_path, TEXT_TABLES)
                self.stdout.write(f"已輸出全文 {text_path}")

        if options["sheets"]:
            written = sync_to_sheets(tables)
            self.stdout.write(f"已同步 Google 試算表（{n} 位受試者）：{', '.join(written)}")
