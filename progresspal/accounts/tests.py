import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from accounts.api_key_session import SESSION_FIELD, load_api_key
from accounts.middleware import UserGroqKeyMiddleware
from accounts.models import EventLog, QuestionLog
from learning.models import Chapter, Unit
from learning.services import llm_model

User = get_user_model()
VALIDATE = "accounts.forms.validate_groq_api_key"


def make_user(username="P01"):
    return User.objects.create_user(username, f"{username}@example.com", settings.PARTICIPANT_PASSWORD,
                                    role="low_prior_student")


class RegisterTest(TestCase):
    def payload(self, **extra):
        data = {"username": " A01 ", "role": "low_prior_student", "api_key": "  gsk_user_key  "}
        data.update(extra)
        return data

    @patch(VALIDATE, return_value=None)
    def test_register_with_three_fields_sets_fixed_password_and_session_key(self, validate):
        resp = self.client.post("/user/register/", self.payload())
        self.assertEqual(resp.status_code, 302)
        validate.assert_called_once_with("gsk_user_key")
        user = User.objects.get(username="A01")
        self.assertTrue(user.check_password(settings.PARTICIPANT_PASSWORD))
        self.assertTrue(user.email.startswith("A01-") and user.email.endswith("@participant.invalid"))
        self.assertEqual(user.nickname, "A01")
        # key 只在 Session（加密），不在使用者資料表任何欄位
        session = self.client.session
        self.assertNotIn("gsk_user_key", session[SESSION_FIELD])
        self.assertNotIn("gsk_user_key", json.dumps(User.objects.filter(pk=user.pk).values().first(), default=str))

    @patch(VALIDATE, return_value="這把 API Key 無效或已過期")
    def test_invalid_key_blocks_registration(self, _):
        resp = self.client.post("/user/register/", self.payload())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "這把 API Key 無效或已過期")
        self.assertFalse(User.objects.filter(username="A01").exists())

    @patch(VALIDATE, return_value=None)
    def test_id_with_space_is_rejected(self, _):
        resp = self.client.post("/user/register/", self.payload(username="A 01"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.exists())

    @patch(VALIDATE, return_value=None)
    def test_duplicate_id_is_rejected(self, _):
        make_user("A01")
        resp = self.client.post("/user/register/", self.payload(username="a01"))
        self.assertContains(resp, "這個編號已經註冊過了")


class LoginAndSessionKeyTest(TestCase):
    def login(self, **extra):
        data = {"account": "P01", "password": settings.PARTICIPANT_PASSWORD, "api_key": "gsk_login_key"}
        data.update(extra)
        return self.client.post("/user/login/", data)

    @patch(VALIDATE, return_value=None)
    def test_login_stores_key_in_session_and_logout_clears_it(self, _):
        make_user()
        self.assertEqual(self.login().status_code, 302)
        request = RequestFactory().get("/")
        request.session = self.client.session
        self.assertEqual(load_api_key(request), "gsk_login_key")
        self.client.get("/user/logout/")
        self.assertNotIn(SESSION_FIELD, self.client.session)

    @patch(VALIDATE, return_value="這把 API Key 無效或已過期")
    def test_login_rejected_with_invalid_key(self, _):
        make_user()
        resp = self.login()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "這把 API Key 無效或已過期")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_requires_key(self):
        make_user()
        resp = self.login(api_key="")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    @patch(VALIDATE, return_value=None)
    def test_session_expires_after_eight_hours(self, _):
        make_user()
        self.login(remember="on")
        self.assertEqual(settings.SESSION_COOKIE_AGE, 8 * 60 * 60)
        self.assertEqual(self.client.session.get_expiry_age(), 8 * 60 * 60)

    @patch(VALIDATE, return_value=None)
    def test_profile_replaces_session_key(self, _):
        user = make_user()
        self.login()
        self.client.post("/user/profile/", {"update_profile": "1", "nickname": "n", "email": user.email,
                                            "role": user.role, "grade": "", "api_key": "gsk_new"})
        request = RequestFactory().get("/")
        request.session = self.client.session
        self.assertEqual(load_api_key(request), "gsk_new")


@override_settings(GROQ_API_KEYS=["gsk_server"])
class KeySelectionAndFallbackTest(TestCase):
    def run_in_request(self, session_key, fn):
        """在 middleware 包住的請求中執行 fn，回傳其結果"""
        request = RequestFactory().get("/")
        request.user = User.objects.filter(username="P01").first() or make_user()
        request.session = self.client.session
        if session_key:
            from accounts.api_key_session import store_api_key
            store_api_key(request, session_key)
        out = {}
        UserGroqKeyMiddleware(lambda r: out.setdefault("v", fn()))(request)
        return out["v"]

    def test_session_key_first_then_server_fallback(self):
        keys = self.run_in_request("gsk_user", lambda: llm_model.get_rotational_client().api_keys)
        self.assertEqual(keys, ["gsk_user", "gsk_server"])

    @override_settings(GROQ_FALLBACK_TO_SERVER_KEYS=False)
    def test_fallback_can_be_disabled(self):
        keys = self.run_in_request("gsk_user", lambda: llm_model.get_rotational_client().api_keys)
        self.assertEqual(keys, ["gsk_user"])

    def test_fallback_flag_only_when_server_key_answers(self):
        def answer_with(index):
            def fn():
                client = llm_model.get_rotational_client()
                client._record_key_use(index)
                return llm_model.fallback_key_used()
            return fn
        self.assertFalse(self.run_in_request("gsk_user", answer_with(0)))
        self.assertTrue(self.run_in_request("gsk_user", answer_with(1)))
        # 沒有個人 key 時用的就是伺服器 key
        self.assertTrue(self.run_in_request("", answer_with(0)))

    def test_context_is_reset_after_request(self):
        self.run_in_request("gsk_user", lambda: None)
        self.assertEqual(llm_model.user_api_key.get(), "")
        self.assertIsNone(llm_model.llm_usage.get())


class FallbackLoggingTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        chapter = Chapter.objects.create(chapter_number="1", title="堆疊與佇列")
        Unit.objects.create(unit_number="1", title="堆疊", chapter=chapter)

    def ask(self, fallback):
        def fake_answer(**kwargs):
            if fallback:
                llm_model.llm_usage.get()["fallback"] = True
            return {"answer": "A", "extended_question": "Q", "hint": "H"}
        with patch("learning.views.main.answer_question", side_effect=fake_answer):
            return self.client.post("/lesson/1/1/study/api/chat/", json.dumps({"user_question": "堆疊是什麼"}),
                                    content_type="application/json")

    def test_fallback_answer_is_flagged_and_logged(self):
        self.assertEqual(self.ask(fallback=True).status_code, 200)
        log = QuestionLog.objects.get()
        self.assertTrue(log.fallback_key_used)
        event = EventLog.objects.get(event_type="fallback_key")
        self.assertEqual(event.question_log, log)
        self.assertEqual(event.detail, {"where": "answer"})

    def test_normal_answer_is_not_flagged(self):
        self.ask(fallback=False)
        self.assertFalse(QuestionLog.objects.get().fallback_key_used)
        self.assertFalse(EventLog.objects.exists())
