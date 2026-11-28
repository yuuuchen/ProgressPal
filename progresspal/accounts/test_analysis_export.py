"""R7 分析資料匯出（docs/SPEC_實驗資料與部署.md 第 4 節）"""
import io
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.analysis_export import COLUMNS, build_tables, sync_to_sheets, write_excel
from accounts.models import EventLog, LearningRecord, QuestionLog
from emotion.models import EmotionRecord

User = get_user_model()


def at(base, seconds):
    return base + timedelta(seconds=seconds)


class AnalysisFixture(TestCase):
    """一位受試者 10 分鐘內的典型紀錄"""

    def setUp(self):
        self.t0 = timezone.now().replace(microsecond=0) - timedelta(hours=1)
        self.user = User.objects.create_user("A01", "a@example.com", "x", role="low_prior_student")
        User.objects.create_user("admin", "admin@example.com", "x", is_staff=True)  # 研究者不列入
        LearningRecord.objects.create(user=self.user, chapter_code="1", unit_code="1",
                                      start_time=self.t0, end_time=at(self.t0, 600))
        # 情緒樣本：confusion ×3（每 5 秒）→ frustration ×3（low_streak 1..3）→ 一筆低信心 → delight
        samples = [("confusion", 0.9, "high", 0)] * 3 + [("frustration", 0.9, "low", 1),
                                                        ("frustration", 0.9, "low", 2),
                                                        ("frustration", 0.9, "low", 3),
                                                        ("delight", 0.2, None, 3),
                                                        ("delight", 0.9, "high", 0)]
        for i, (emotion, conf, engagement, streak) in enumerate(samples):
            EmotionRecord.objects.create(user=self.user, emotion=emotion, confidence=conf,
                                         low_confidence=conf < 0.5, engagement=engagement, low_streak=streak,
                                         timestamp=at(self.t0, 10 + 5 * i))
        self.ev("face_fail", 52, reason="no_face")
        self.ev("face_fail", 53, reason="no_face")
        self.ev("extended_q_shown", 1, source="materials")
        self.ev("proactive_trigger", 41, low_streak=3)
        self.ev("hint_shown", 41, source="proactive")
        self.ev("hint_click", 45, source="proactive")          # 觸發後 4 秒點擊，且在低參與期間
        self.q = QuestionLog.objects.create(user=self.user, chapter_code="1", unit_code="1",
                                            type="answer_extend_question", stu_input="我的回答", answer="很好",
                                            system_question="延伸題", hint_is_used=True, engagement="low",
                                            response_seconds=3.5)
        QuestionLog.objects.filter(pk=self.q.pk).update(created_at=at(self.t0, 70))
        self.ev("extended_q_answered", 70, question_log=self.q)
        self.ev("extended_q_shown", 70, question_log=self.q, source="answer")
        self.ev("hint_click", 300, source="proactive")          # 之後沒有回應延伸題 → 不算有效互動
        q2 = QuestionLog.objects.create(user=self.user, chapter_code="1", unit_code="1", type="question",
                                        stu_input="堆疊是什麼", answer="答案", response_seconds=1.5,
                                        fallback_key_used=True)
        QuestionLog.objects.filter(pk=q2.pk).update(created_at=at(self.t0, 400))
        self.ev("fallback_key", 400, question_log=q2, where="answer")
        self.tables = build_tables(group="adaptive")

    def ev(self, event_type, seconds, question_log=None, **detail):
        return EventLog.objects.create(user=self.user, event_type=event_type, chapter_code="1", unit_code="1",
                                       question_log=question_log, detail=detail, created_at=at(self.t0, seconds))

    def summary(self):
        headers, rows = self.tables["summary"]
        self.assertEqual(len(rows), 1)  # 研究者帳號不列入
        return dict(zip(headers, rows[0]))


class BuildTablesTest(AnalysisFixture):
    def test_columns_match_spec(self):
        for name, (headers, rows) in self.tables.items():
            self.assertEqual(headers, COLUMNS[name])
            for row in rows:
                self.assertEqual(len(row), len(headers), name)
        self.assertIn("Total_Struggle_Time", COLUMNS["log"])
        self.assertNotIn("user_input", COLUMNS["log"])  # 全文只在 log_text

    def test_summary_metrics(self):
        s = self.summary()
        self.assertEqual(s["total_duration_s"], 600.0)
        self.assertEqual((s["n_samples"], s["n_face_fail"]), (8, 2))
        self.assertEqual(s["valid_sample_ratio"], round(7 / 10, 4))
        self.assertFalse(s["exclude_flag"])
        self.assertEqual((s["proactive_trigger_count"], s["proactive_click_rate"], s["trigger_to_click_s"]),
                         (1, 1.0, 4.0))
        self.assertEqual((s["hint_click_count"], s["hint_click_in_low_window"]), (2, 1))
        self.assertEqual(s["effective_interaction_rate"], 0.5)
        self.assertEqual((s["question_count"], s["extended_answer_count"]), (1, 1))
        self.assertEqual(s["questions_per_min"], 0.1)
        self.assertEqual((s["avg_response_s"], s["fallback_key_count"]), (2.5, 1))
        self.assertEqual(s["struggle_time_s"], 15.0)  # 3 筆困惑，每筆到下一筆 5 秒
        self.assertEqual(s["pct_confusion"], round(3 / 7, 4))
        self.assertEqual(s["pct_negative"], round(3 / 7, 4))
        self.assertEqual(s["pct_high_engagement"], round(4 / 7, 4))
        self.assertEqual((s["crt_count"], s["crt_mean_s"]), (1, 20))  # frustration@25s → delight@45s（低信心那筆不算）

    def test_log_row_keeps_original_definitions_and_new_columns(self):
        headers, rows = self.tables["log"]
        row = dict(zip(headers, rows[0]))
        self.assertEqual(row["Task_Latency"], 70.0)          # 從進入單元到第一次回應
        self.assertEqual(row["Total_Struggle_Time"], 15.0)
        self.assertEqual(row["hint_source"], "proactive")
        self.assertEqual((row["input_len"], row["reply_len"]), (4, 2))
        self.assertEqual(dict(zip(headers, rows[1]))["fallback_key_used"], True)

    def test_emotion_rows_have_unit_and_elapsed(self):
        headers, rows = self.tables["emotion"]
        first = dict(zip(headers, rows[0]))
        self.assertEqual((first["unit_code"], first["elapsed_s"], first["engage_level"]), ("1", 10.0, "high"))
        self.assertTrue(dict(zip(headers, rows[6]))["low_confidence"])

    def test_text_table_is_separate(self):
        headers, rows = self.tables["log_text"]
        self.assertEqual(dict(zip(headers, rows[0]))["user_input"], "我的回答")


class ExcelAndAdminTest(AnalysisFixture):
    def test_excel_has_numeric_sheets_only(self):
        from openpyxl import load_workbook
        buffer = io.BytesIO()
        write_excel(self.tables, buffer, ["summary", "emotion", "duration", "log", "events"])
        workbook = load_workbook(io.BytesIO(buffer.getvalue()))
        self.assertEqual(workbook.sheetnames, ["summary", "emotion", "duration", "log", "events"])
        self.assertEqual(workbook["summary"]["A2"].value, "A01")

    def test_admin_downloads_require_staff(self):
        self.assertEqual(self.client.get("/admin/experiment/export-excel/").status_code, 302)
        self.client.force_login(self.user)  # 受試者不是 staff
        self.assertEqual(self.client.get("/admin/experiment/export-excel/").status_code, 302)
        self.client.force_login(User.objects.get(username="admin"))
        resp = self.client.get("/admin/experiment/export-excel/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f"{settings.EXPERIMENT_GROUP}_analysis_", resp["Content-Disposition"])
        self.assertEqual(self.client.get("/admin/experiment/export-text-excel/").status_code, 200)

    def test_admin_index_shows_export_buttons(self):
        admin = User.objects.get(username="admin")
        admin.is_superuser = True
        admin.save()
        self.client.force_login(admin)
        html = self.client.get("/admin/").content.decode()
        self.assertIn("同步到 Google 試算表", html)
        self.assertIn("/admin/experiment/export-excel/", html)


class FakeWorksheet:
    def __init__(self, title):
        self.title, self.values = title, None

    def clear(self):
        self.values = None

    def resize(self, rows, cols):
        pass

    def update(self, values, range_name, value_input_option):
        self.values = values


class FakeSpreadsheet:
    def __init__(self, titles=()):
        self.sheets = {t: FakeWorksheet(t) for t in titles}

    def worksheet(self, title):
        if title not in self.sheets:
            raise LookupError(title)
        return self.sheets[title]

    def add_worksheet(self, title, rows, cols):
        self.sheets[title] = FakeWorksheet(title)
        return self.sheets[title]

    def worksheets(self):
        return list(self.sheets.values())


class FakeClient:
    def __init__(self, books):
        self.books = books

    def open_by_key(self, key):
        return self.books[key]


@override_settings(ANALYSIS_SHEET_ID="analysis", TEXT_SHEET_ID="text")
class SheetsSyncTest(AnalysisFixture):
    def test_writes_group_prefixed_tabs_and_creates_all_summary_once_both_exist(self):
        analysis, text = FakeSpreadsheet(["control_summary"]), FakeSpreadsheet()
        written = sync_to_sheets(self.tables, "adaptive", FakeClient({"analysis": analysis, "text": text}))
        for name in ["summary", "emotion", "duration", "log", "events"]:
            self.assertIn(f"adaptive_{name}", analysis.sheets)
        self.assertEqual(analysis.sheets["adaptive_summary"].values[1][0], "A01")
        self.assertIn("all_summary", analysis.sheets)
        self.assertIn("adaptive_log_text", text.sheets)
        self.assertNotIn("adaptive_log_text", analysis.sheets)
        self.assertIn("all_summary", written)

    @override_settings(ANALYSIS_SHEET_ID="")
    def test_requires_sheet_id(self):
        with self.assertRaises(RuntimeError):
            sync_to_sheets(self.tables, "adaptive", FakeClient({}))
