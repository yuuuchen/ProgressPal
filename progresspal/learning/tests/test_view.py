import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from learning.models import Chapter, Unit
from accounts.models import QuestionLog

User = get_user_model()

class LearningViewsTest(TestCase):
    def setUp(self):
        """建立測試環境：使用者、章節、單元"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_mis",
            email="test_mis@gmail.com",
            password="MISMIS2486",
            role="student",
            emotions="['happy', 'neutral']"
        )
        self.client.login(username="test_mis", password="MISMIS2486")

        # 建立章節與單元
        self.chapter = Chapter.objects.create(chapter_number="C01", title="資料結構導論")
        self.unit = Unit.objects.create(unit_number="U01", title="陣列", chapter=self.chapter)

    @patch("learning.views.main.display_materials")
    @patch("learning.views.compute_engagement")
    def test_generate_materials_view(self, mock_engagement, mock_display):
        """測試教材生成 view"""
        mock_engagement.return_value = "high"
        mock_display.return_value = {
            "teaching": "這是教學內容",
            "example": "這是範例內容",
            "summary": "這是重點摘要",
            "extended_questions": ["什麼是陣列？", "陣列與串列的差別？"]
        }

        url = reverse("learning:generate_materials", args=["C01", "U01"])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "這是教學內容")
        self.assertContains(response, "這是範例內容")
        self.assertTemplateUsed(response, "learning/study.html")

    @patch("learning.views.main.answer_question")
    @patch("learning.views.compute_engagement")
    def test_answer_question_view(self, mock_engagement, mock_answer):
        """測試教材問答 view (JSON 回傳)"""
        mock_engagement.return_value = "medium"
        mock_answer.return_value = {
            "answer": "陣列是一種連續記憶體結構。",
            "extended_question": "那串列又是什麼？"
        }

        url = reverse("learning:answer_question", args=["C01", "U01"])
        data = {
            "question_choice": "direct",
            "user_question": "請問什麼是陣列？"
        }

        response = self.client.post(
            url,
            json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertIn("answer", result)
        self.assertIn("extended_questions", result)
        self.assertEqual(result["answer"], "陣列是一種連續記憶體結構。")

        # 檢查 QuestionLog 是否被建立
        self.assertTrue(QuestionLog.objects.filter(user=self.user).exists())

    def tearDown(self):
        self.client.logout()
