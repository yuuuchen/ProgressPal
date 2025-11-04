import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from learning.models import Chapter, Unit
from accounts.models import QuestionLog

User = get_user_model()


class LearningViewsIntegrationTest(TestCase):
    """整合測試：確認 learning/views.py 的功能能正常執行"""

    def setUp(self):
        """建立測試資料：使用者、章節、單元"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_mis",
            email="test_mis@gmail.com",
            password="MISMIS2486",
            role="student"
        )
        self.user.emotions = ['喜悅', '投入']
        self.client.login(username="test_mis", password="MISMIS2486")

        # 建立章節與單元
        self.chapter = Chapter.objects.create(
            chapter_number="1", title="陣列(Array)"
        )
        self.unit = Unit.objects.create(
            unit_number="1", title="陣列概論", chapter=self.chapter
        )

    @patch("learning.views.compute_engagement")
    @patch("learning.services.main.client.models.generate_content")
    def test_generate_materials_view(self, mock_gemini, mock_engagement):
        """測試教材生成 view 實際執行是否正常"""
        mock_engagement.return_value = "high"

        # 模擬 Gemini API 回傳內容
        mock_gemini.return_value.text = """
        教學內容：
        - 陣列是一種線性資料結構。
        範例：
        - int arr[5];
        摘要：
        - 陣列可用索引存取。
        延伸問題：
        - 陣列與串列有何不同？
        """

        url = reverse("learning:generate_materials", args=["1", "1"])
        response = self.client.post(url)

        # 驗證回傳
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning/study.html")
        self.assertIn("這是教學內容", response.content.decode("utf-8")) or self.assertIn("陣列", response.content.decode("utf-8"))
        print("\n✅ generate_materials_view 測試成功")

    @patch("learning.views.compute_engagement")
    @patch("learning.services.main.client.models.generate_content")
    def test_answer_question_view(self, mock_gemini, mock_engagement):
        """測試教材問答 view (JSON 回傳) 實際執行是否正常"""
        mock_engagement.return_value = "medium"

        # 模擬 Gemini 問答回傳
        mock_gemini.return_value.text = """
        答案：
        陣列是一種連續記憶體結構。
        延伸問題：
        那串列又是什麼？
        """

        url = reverse("learning:answer_question", args=["1", "1"])
        data = {
            "question_choice": "direct",
            "user_question": "請問什麼是二維陣列？"
        }

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json"
        )

        # 驗證回傳
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)

        self.assertIn("answer", result)
        self.assertIn("extended_questions", result)
        self.assertTrue(QuestionLog.objects.filter(user=self.user).exists())
        print("\n✅ answer_question_view 測試成功")

    def tearDown(self):
        self.client.logout()