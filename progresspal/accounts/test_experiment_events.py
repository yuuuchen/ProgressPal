"""R4 表單連結、R5 事件紀錄、R6 參與度統一（docs/SPEC_實驗資料與部署.md）"""
import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import EventLog, LearningRecord, QuestionLog
from emotion.models import EmotionRecord
from emotion.services.preprocess import NoFaceDetectedError
from emotion.services.utils import current_engagement, update_engagement_state
from learning.models import Chapter, Unit

User = get_user_model()


def make_user(username="P01"):
    return User.objects.create_user(username, f"{username}@example.com", settings.PARTICIPANT_PASSWORD,
                                    role="low_prior_student")


class FormLinkTest(TestCase):
    @override_settings(FORM_PRETEST_URL="https://forms.example/pre?entry.1={participant_id}",
                       FORM_POSTTEST_URL="https://forms.example/post")
    def test_navbar_has_two_form_links_with_participant_id(self):
        self.client.force_login(make_user("A07"))
        html = self.client.get("/lesson/").content.decode()
        self.assertIn('href="https://forms.example/pre?entry.1=A07"', html)
        self.assertIn('href="https://forms.example/post"', html)
        self.assertEqual(html.count('data-form-link='), 2)
        self.assertIn("experiment_events.js", html)

    @override_settings(FORM_PRETEST_URL="https://forms.example/pre?entry.1={participant_id}",
                       FORM_POSTTEST_URL="https://forms.example/post")
    def test_logged_out_navbar_also_has_only_two_form_links(self):
        html = self.client.get("/user/register/").content.decode()
        self.assertIn('href="https://forms.example/pre?entry.1="', html)
        self.assertEqual(html.count('data-form-link='), 2)
        self.assertNotIn("PreTestDropdown", html)


class ClientEventEndpointTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def post(self, body):
        return self.client.post("/events/", json.dumps(body), content_type="application/json")

    def test_accepts_client_event_types(self):
        for event_type in ["proactive_trigger", "hint_shown", "hint_click", "form_link_click"]:
            resp = self.post({"event_type": event_type, "chapter_code": "1", "unit_code": "2",
                              "detail": {"source": "manual"}})
            self.assertEqual(resp.status_code, 200, event_type)
        event = EventLog.objects.get(event_type="hint_click")
        self.assertEqual((event.user, event.chapter_code, event.unit_code, event.detail),
                         (self.user, "1", "2", {"source": "manual"}))

    def test_rejects_server_only_or_unknown_types_and_bad_detail(self):
        self.assertEqual(self.post({"event_type": "fallback_key"}).status_code, 400)
        self.assertEqual(self.post({"event_type": "nope"}).status_code, 400)
        self.assertEqual(self.post({"event_type": "hint_click", "detail": "x"}).status_code, 400)
        self.assertEqual(self.post({"event_type": "hint_click", "detail": {"x": "y" * 3000}}).status_code, 400)
        self.assertFalse(EventLog.objects.exists())

    def test_requires_login_and_csrf(self):
        from django.test import Client
        self.assertEqual(Client().post("/events/", "{}", content_type="application/json").status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        resp = strict.post("/events/", json.dumps({"event_type": "hint_click"}), content_type="application/json")
        self.assertEqual(resp.status_code, 403)


class ServerEventTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        chapter = Chapter.objects.create(chapter_number="1", title="堆疊與佇列")
        Unit.objects.create(unit_number="1", title="堆疊", chapter=chapter)

    @patch("learning.views.main.display_materials",
           return_value={"guide": "g", "core": "c", "example": "", "extended_question": "Q1", "hint": "H"})
    def test_unit_enter_and_leave_and_extended_question_flow(self, _):
        self.assertEqual(self.client.get("/lesson/1/1/study/").status_code, 200)
        record = LearningRecord.objects.get()
        with patch("learning.views.main.answer_question",
                   return_value={"answer": "A", "extended_question": "Q2", "hint": "H2"}):
            self.client.post("/lesson/1/1/study/api/chat/",
                             json.dumps({"question_choice": "extended", "user_question": "我的回答"}),
                             content_type="application/json")
        # duration.js 每 10 秒送一次心跳：只保留一筆 unit_leave，內容為最新一次
        for seconds in (10, 20, 42):
            self.client.post("/lesson/end/", json.dumps({"id": record.id, "duration_seconds": seconds}),
                             content_type="application/json")
        types = list(EventLog.objects.values_list("event_type", flat=True))
        self.assertEqual(types, ["unit_enter", "extended_q_shown", "extended_q_answered", "extended_q_shown",
                                 "unit_leave"])
        log = QuestionLog.objects.get()
        self.assertEqual(EventLog.objects.get(event_type="extended_q_answered").question_log, log)
        leave = EventLog.objects.get(event_type="unit_leave")
        self.assertEqual(leave.detail, {"record_id": record.id, "duration_seconds": 42.0})
        record.refresh_from_db()
        self.assertEqual(leave.created_at, record.end_time)

    @patch("emotion.views.preprocess_frame", side_effect=NoFaceDetectedError("未偵測到臉"))
    def test_face_fail_is_logged(self, _):
        from django.core.files.uploadedfile import SimpleUploadedFile
        resp = self.client.post("/emotion/detect/", {"image": SimpleUploadedFile("f.jpg", b"x", "image/jpeg")})
        self.assertEqual(resp.status_code, 422)
        event = EventLog.objects.get(event_type="face_fail")
        self.assertEqual(event.detail["reason"], "no_face")


class EngagementStateTest(TestCase):
    """參與度：最近 10 筆有效樣本、信心度 < 0.5 不計入、low_streak 連續計數"""

    def setUp(self):
        self.user = make_user()
        self.t0 = timezone.now()
        self.n = 0

    def add(self, emotion, confidence=0.9):
        self.n += 1
        record = EmotionRecord.objects.create(user=self.user, emotion=emotion, confidence=confidence,
                                              timestamp=self.t0 + timedelta(seconds=5 * self.n))
        return update_engagement_state(record)

    def test_streak_counts_consecutive_low_and_resets_on_high(self):
        first = self.add("boredom")      # 單筆 boredom → EMA 0.0 → low
        self.assertEqual((first.engagement, first.low_streak), ("low", 1))
        self.assertEqual(self.add("boredom").low_streak, 2)
        self.assertEqual(self.add("frustration").low_streak, 3)
        # 連續多筆正向後 EMA 回升到 0.5 以上，streak 歸零
        states = [self.add("engagement") for _ in range(4)]
        self.assertEqual(states[-1].engagement, "high")
        self.assertEqual(states[-1].low_streak, 0)

    def test_low_confidence_sample_neither_counts_nor_breaks_streak(self):
        self.add("boredom")
        self.add("boredom")
        noisy = self.add("delight", confidence=0.3)
        self.assertTrue(noisy.low_confidence)
        self.assertIsNone(noisy.engagement)
        self.assertEqual(noisy.low_streak, 2)
        self.assertEqual(self.add("boredom").low_streak, 3)

    def test_current_engagement_uses_latest_valid_sample(self):
        self.assertEqual(current_engagement(self.user), "high")  # 尚無樣本
        self.add("boredom")
        self.add("delight", confidence=0.2)
        self.assertEqual(current_engagement(self.user), "low")

    @patch("emotion.views.predict_emotion", return_value={"emotion": "無聊", "confidence": 0.9})
    @patch("emotion.views.preprocess_frame", return_value=object())
    def test_detect_api_returns_streak_and_stores_state(self, *_):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.user)
        for expected in (1, 2, 3):
            resp = self.client.post("/emotion/detect/",
                                    {"image": SimpleUploadedFile("f.jpg", b"x", "image/jpeg")}).json()
            self.assertEqual((resp["engagement"], resp["low_streak"], resp["low_confidence"]),
                             ("low", expected, False))
        self.assertEqual(list(EmotionRecord.objects.values_list("low_streak", flat=True)), [1, 2, 3])
