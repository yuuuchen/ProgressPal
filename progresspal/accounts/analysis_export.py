"""
實驗分析資料匯出（docs/SPEC_實驗資料與部署.md 第 4 節、R7）

build_tables() 從資料庫產生分析用資料表，供以下三種輸出共用：
- write_excel()：管理後台「下載 Excel」
- sync_to_sheets()：Google 試算表（管理後台按鈕、每 10 分鐘自動同步）
- 管理指令 `python manage.py export_analysis`

資料表：emotion、duration、log、events、summary（數值，寫入分析試算表）
        log_text（對話全文，寫入權限較嚴的全文試算表）
試算表中不出現姓名、email、API key；系統內章節測驗結果不匯出。
"""
import json
from bisect import bisect_right
from datetime import timedelta
from statistics import mean

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import EventLog, LearningRecord, QuestionLog
from emotion.models import EmotionRecord

NUMERIC_TABLES = ["summary", "emotion", "duration", "log", "events"]
TEXT_TABLES = ["log_text"]

NEGATIVE = {"boredom", "frustration"}
POSITIVE = {"engagement", "delight", "surprise"}
LABELS = dict(EmotionRecord.EMOTION_CHOICES)  # 英文代碼 → 中文

LOW_WINDOW_S = 30        # RQ1：點擊前 30 秒內出現過連續低參與（low_streak ≥ 3）
LOW_STREAK_TRIGGER = 3
PROACTIVE_CLICK_S = 60   # 主動介入觸發後 60 秒內點擊視為回應
MAX_SAMPLE_GAP_S = 15    # 整段困惑時間：相鄰兩筆樣本的時間差最多算 15 秒（避免離開頁面的空檔被算進去）
EXCLUDE_BELOW = 0.5      # 有效樣本比例低於 50% 標記排除


def _fmt(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def _sec(delta):
    return round(delta.total_seconds(), 2)


def _avg(values):
    values = [v for v in values if v is not None]
    return round(mean(values), 2) if values else ""


def _ratio(num, den):
    return round(num / den, 4) if den else ""


class _Sessions:
    """一位受試者的學習時段（LearningRecord），用來找某個時間點所在的單元與 elapsed_s"""

    def __init__(self, records):
        self.records = sorted(records, key=lambda r: r.start_time)
        self.starts = [r.start_time for r in self.records]

    def at(self, t):
        i = bisect_right(self.starts, t) - 1
        if i < 0:
            return None
        record = self.records[i]
        end = record.end_time
        next_start = self.starts[i + 1] if i + 1 < len(self.starts) else None
        if end is not None and t > end + timedelta(seconds=MAX_SAMPLE_GAP_S) and (next_start is None or t < next_start):
            return None  # 已離開單元一段時間（例如停留在其他頁面）
        return record

    def locate(self, t, chapter=None, unit=None):
        record = self.at(t)
        if record is None:
            return chapter, unit, ""
        return (chapter or record.chapter_code, unit or record.unit_code, _sec(t - record.start_time))


def _crt_and_struggle(samples, until=None, cap=None):
    """
    沿用 accounts/services/generate_csv.py 的定義：
    - CRT：進入負向情緒（無聊、挫折）到轉為正向情緒（投入、喜悅、驚訝）的秒數
    - 困惑時間：連續「困惑」的時間，到下一筆非困惑樣本（或 until）為止
    cap 有值時每段相鄰樣本的時間差最多算 cap 秒（整段學習期間統計用）
    """
    crt, struggle = [], 0.0
    negative_start, confusion_start, prev_t = None, None, None
    for t, emotion in samples:
        if emotion in NEGATIVE and negative_start is None:
            negative_start = t
        elif emotion in POSITIVE and negative_start is not None:
            crt.append(int((t - negative_start).total_seconds()))
            negative_start = None
        if cap is not None:
            if prev_t is not None and prev_emotion == "confusion":
                struggle += min((t - prev_t).total_seconds(), cap)
            prev_t, prev_emotion = t, emotion
        elif emotion == "confusion":
            confusion_start = confusion_start or t
        elif confusion_start is not None:
            struggle += (t - confusion_start).total_seconds()
            confusion_start = None
    if cap is None and confusion_start is not None and until is not None and until > confusion_start:
        struggle += (until - confusion_start).total_seconds()
    return crt, round(struggle, 2)


def participants():
    return get_user_model().objects.filter(is_staff=False, is_superuser=False).order_by("username")


def build_tables(group=None):
    """回傳 {資料表名稱: (欄位名稱 list, 資料列 list)}"""
    group = group or settings.EXPERIMENT_GROUP
    tables = {name: [] for name in NUMERIC_TABLES + TEXT_TABLES}

    for user in participants():
        sid = user.username
        records = list(LearningRecord.objects.filter(user=user))
        sessions = _Sessions(records)
        emotions = list(EmotionRecord.objects.filter(user=user).order_by("timestamp", "pk"))
        questions = list(QuestionLog.objects.filter(user=user).order_by("created_at", "pk"))
        events = list(EventLog.objects.filter(user=user).order_by("created_at", "pk"))

        # ① emotion
        for e in emotions:
            chapter, unit, elapsed = sessions.locate(e.timestamp)
            tables["emotion"].append([group, sid, chapter or "", unit or "", _fmt(e.timestamp), elapsed, e.emotion,
                                      round(e.confidence, 4), e.low_confidence, e.engagement or "", e.low_streak])

        # ② duration
        for r in sorted(records, key=lambda r: r.start_time):
            duration = _sec(r.end_time - r.start_time) if r.end_time else ""
            tables["duration"].append([group, sid, r.chapter_code, r.unit_code, duration,
                                       _fmt(r.start_time), _fmt(r.end_time)])

        # ③ log（沿用 generate_csv 的 Task_Latency、CRT_Sequence、Total_Struggle_Time 定義）
        hint_clicks = [ev for ev in events if ev.event_type == "hint_click"]
        last_event_time, current_unit = None, None
        for q in questions:
            q_time = q.created_at
            if q.unit_code != current_unit:
                last_event_time, current_unit = None, q.unit_code
            starts = [r.start_time for r in records if r.unit_code == q.unit_code and r.start_time <= q_time]
            if starts and (last_event_time is None or max(starts) > last_event_time):
                last_event_time = max(starts)
            if last_event_time is None:
                last_event_time = q_time
            interval = [(e.timestamp, e.emotion) for e in emotions if last_event_time <= e.timestamp <= q_time]
            crt, struggle = _crt_and_struggle(interval, until=q_time)
            task_latency = _sec(q_time - last_event_time)
            last_event_time = q_time

            hint_source = "none"
            if q.hint_is_used:
                clicks = [c for c in hint_clicks if c.created_at <= q_time]
                hint_source = clicks[-1].detail.get("source", "") if clicks else ""
            tables["log"].append([
                _fmt(q_time), sid, user.role, group, q.chapter_code, q.unit_code,
                "[" + ", ".join(e for _, e in interval) + "]", q.engagement or "",
                "[" + ", ".join(map(str, crt)) + "]", struggle, q.type, q.hint_is_used, _fmt(q.click_time),
                task_latency, q.pk, hint_source, q.fallback_key_used,
                "" if q.response_seconds is None else round(q.response_seconds, 2),
                len(q.stu_input or ""), len(q.answer or ""),
            ])
            tables["log_text"].append([q.pk, sid, group, _fmt(q_time), q.stu_input or "", q.answer or "",
                                       q.system_question or ""])

        # ④ events
        for ev in events:
            chapter, unit, elapsed = sessions.locate(ev.created_at, ev.chapter_code, ev.unit_code)
            tables["events"].append([_fmt(ev.created_at), elapsed, sid, group, chapter or "", unit or "",
                                     ev.event_type, ev.question_log_id or "",
                                     json.dumps(ev.detail, ensure_ascii=False) if ev.detail else ""])

        tables["summary"].append(_summary_row(group, user, records, emotions, questions, events))

    return {name: (COLUMNS[name], rows) for name, rows in tables.items()}


def _summary_row(group, user, records, emotions, questions, events):
    total_s = sum(_sec(r.end_time - r.start_time) for r in records if r.end_time)
    valid = [e for e in emotions if not e.low_confidence]
    n_face_fail = sum(1 for ev in events if ev.event_type == "face_fail")
    valid_ratio = _ratio(len(valid), len(emotions) + n_face_fail)

    triggers = [ev for ev in events if ev.event_type == "proactive_trigger"]
    clicks = [ev for ev in events if ev.event_type == "hint_click"]
    trigger_delays = []
    for trig in triggers:
        later = [c for c in clicks if trig.created_at <= c.created_at <= trig.created_at + timedelta(seconds=PROACTIVE_CLICK_S)]
        if later:
            trigger_delays.append(_sec(later[0].created_at - trig.created_at))

    low_moments = [e.timestamp for e in valid if e.low_streak >= LOW_STREAK_TRIGGER]
    clicks_in_low = sum(
        1 for c in clicks
        if any(c.created_at - timedelta(seconds=LOW_WINDOW_S) <= t <= c.created_at for t in low_moments))

    # 有效互動：點擊提示後，在下一個延伸提問出現之前回應了延伸提問
    effective = 0
    for c in clicks:
        for ev in events:
            if (ev.created_at, ev.pk) <= (c.created_at, c.pk):
                continue
            if ev.event_type == "extended_q_answered":
                effective += 1
                break
            if ev.event_type == "extended_q_shown":
                break

    question_count = sum(1 for q in questions if q.type == "question")
    extended_count = sum(1 for q in questions if q.type == "answer_extend_question")
    crt, struggle = _crt_and_struggle([(e.timestamp, e.emotion) for e in valid], cap=MAX_SAMPLE_GAP_S)
    counts = {code: sum(1 for e in valid if e.emotion == code) for code in LABELS}

    return [
        user.username, group, user.role, round(total_s, 2),
        len(emotions), n_face_fail, valid_ratio, valid_ratio == "" or valid_ratio < EXCLUDE_BELOW,
        len(triggers), _ratio(len(trigger_delays), len(triggers)), _avg(trigger_delays),
        len(clicks), clicks_in_low,
        _avg([q.response_seconds for q in questions]), sum(1 for ev in events if ev.event_type == "fallback_key"),
        question_count, round(question_count / (total_s / 60), 3) if total_s else "", extended_count,
        _ratio(effective, len(clicks)),
        struggle, _ratio(struggle, total_s),
        _ratio(sum(1 for e in valid if e.engagement == "high"), len(valid)),
        _ratio(counts["boredom"] + counts["frustration"], len(valid)),
        _ratio(counts["confusion"], len(valid)),
        *[_ratio(counts[code], len(valid)) for code in LABELS],
        len(crt), _avg(crt),
    ]


COLUMNS = {
    "emotion": ["system_type", "student_id", "chapter_code", "unit_code", "timestamp", "elapsed_s", "emotion",
                "confidence", "low_confidence", "engage_level", "low_streak"],
    "duration": ["system_type", "student_id", "chapter_code", "unit_code", "duration_seconds", "start_time",
                 "end_time"],
    "log": ["timestamp", "student_id", "role_group", "system_type", "chapter_code", "unit_code", "emotion",
            "engage_level", "CRT_Sequence", "Total_Struggle_Time", "action_type", "hint_is_used", "click_time",
            "Task_Latency", "log_id", "hint_source", "fallback_key_used", "response_s", "input_len", "reply_len"],
    "events": ["timestamp", "elapsed_s", "student_id", "system_type", "chapter_code", "unit_code", "event_type",
               "related_log_id", "detail"],
    "summary": ["student_id", "system_type", "role_group", "total_duration_s",
                "n_samples", "n_face_fail", "valid_sample_ratio", "exclude_flag",
                "proactive_trigger_count", "proactive_click_rate", "trigger_to_click_s",
                "hint_click_count", "hint_click_in_low_window",
                "avg_response_s", "fallback_key_count",
                "question_count", "questions_per_min", "extended_answer_count", "effective_interaction_rate",
                "struggle_time_s", "struggle_ratio",
                "pct_high_engagement", "pct_negative", "pct_confusion",
                *[f"pct_{LABELS[code]}" for code in LABELS],
                "crt_count", "crt_mean_s"],
    "log_text": ["log_id", "student_id", "system_type", "timestamp", "user_input", "system_reply",
                 "extended_question"],
}


# ===== 輸出 =====

def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def write_excel(tables, target, names=None):
    """把指定的資料表寫成 Excel（每個資料表一個工作表）。target 為檔案路徑或可寫入的 binary stream"""
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    for name in names or list(tables):
        headers, rows = tables[name]
        sheet = workbook.create_sheet(name)
        sheet.append(headers)
        for row in rows:
            sheet.append([_cell(v) for v in row])
        sheet.freeze_panes = "A2"
    workbook.save(target)


def _sheets_client():
    import google.auth
    import gspread

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(credentials)


def _replace_worksheet(spreadsheet, title, headers, rows):
    values = [headers] + [[_cell(v) for v in row] for row in rows]
    try:
        sheet = spreadsheet.worksheet(title)
    except Exception:  # gspread.WorksheetNotFound
        sheet = spreadsheet.add_worksheet(title=title, rows=len(values), cols=len(headers))
    sheet.clear()
    sheet.resize(rows=max(len(values), 2), cols=len(headers))
    sheet.update(values=values, range_name="A1", value_input_option="RAW")


ALL_SUMMARY_FORMULA = "={adaptive_summary!A1:AZ; control_summary!A2:AZ}"


def sync_to_sheets(tables, group=None, client=None):
    """
    數值資料寫入 ANALYSIS_SHEET_ID、全文寫入 TEXT_SHEET_ID。
    分頁名稱加組別前綴（例如 adaptive_summary），每組只覆寫自己的分頁；
    分析試算表另有 all_summary 分頁以公式合併兩組（不存在時才建立）。
    回傳寫入的分頁名稱 list。
    """
    group = group or settings.EXPERIMENT_GROUP
    if not settings.ANALYSIS_SHEET_ID:
        raise RuntimeError("尚未設定 ANALYSIS_SHEET_ID（分析試算表的 ID）")
    client = client or _sheets_client()
    written = []

    analysis = client.open_by_key(settings.ANALYSIS_SHEET_ID)
    for name in NUMERIC_TABLES:
        headers, rows = tables[name]
        _replace_worksheet(analysis, f"{group}_{name}", headers, rows)
        written.append(f"{group}_{name}")
    existing = {ws.title for ws in analysis.worksheets()}
    if "all_summary" not in existing and {"adaptive_summary", "control_summary"} <= existing:
        sheet = analysis.add_worksheet(title="all_summary", rows=2, cols=1)
        sheet.update(values=[[ALL_SUMMARY_FORMULA]], range_name="A1", value_input_option="USER_ENTERED")
        written.append("all_summary")

    if settings.TEXT_SHEET_ID:
        text = client.open_by_key(settings.TEXT_SHEET_ID)
        for name in TEXT_TABLES:
            headers, rows = tables[name]
            _replace_worksheet(text, f"{group}_{name}", headers, rows)
            written.append(f"{group}_{name}（全文）")
    return written
