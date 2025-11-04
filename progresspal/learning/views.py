import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from learning.models import Chapter, Unit
from accounts.models import QuestionLog

User = get_user_model()


class LearningViewsIntegrationTest(TestCase):
    """整合測試 learning/views.py 各功能"""

    def setUp(self):
        """建立測試資料"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="student",
            email="student@test.com",
            password="TestPass123",
            role="student"
        )
        self.client.login(username="student", password="TestPass123")

        # 模擬 CustomUser 欄位
        self.user.emotions = ['喜悅', '專注']

    def test_generate_materials_view(self):
        """
        測試教材生成功能是否可正常執行：
        1. 呼叫 view
        2. 驗證渲染的模板
        3. 驗證 context 有教材內容
        """
        # 用 patch 讓服務端不連雲端 API，只回傳假資料
        from learning.views import main
        main.display_materials = lambda c, u, e, r: {
            "teaching": "這是教學內容",
            "example": "這是範例內容",
            "summary": "這是重點摘要",
            "extended_questions": ["什麼是陣列？"]
        }

        url = reverse("learning:generate_materials", args=["1", "1"])
        response = self.client.post(url)

        # 測試是否成功渲染教材頁面
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning/study.html")
        self.assertContains(response, "這是教學內容")
        self.assertContains(response, "什麼是陣列？")

    def test_answer_question_view(self):
        """
        測試教材問答功能：
        1. 送出模擬提問 JSON
        2. 檢查回傳內容是否含有答案與延伸問題
        3. 確認資料庫有紀錄提問
        """
        from learning.views import main
        main.answer_question = lambda **kwargs: {
            "answer": "陣列是一種連續記憶體結構。",
            "extended_question": "那串列又是什麼？"
        }

        url = reverse("learning:answer_question", args=["1", "1"])
        data = {
            "question_choice": "direct",
            "user_question": "請問什麼是陣列？"
        }

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)

        # 驗證 JSON 結構
        self.assertIn("answer", result)
        self.assertIn("extended_questions", result)
        self.assertEqual(result["answer"], "陣列是一種連續記憶體結構。")
        self.assertIn("那串列又是什麼？", result["extended_questions"])

        # 驗證 QuestionLog 是否有寫入
        self.assertTrue(
            QuestionLog.objects.filter(
                user=self.user,
                question__contains="陣列"
            ).exists()
        )

    def test_invalid_request(self):
        """測試錯誤的請求格式"""
        url = reverse("learning:answer_question", args=["1", "1"])
        response = self.client.get(url)  # GET 而非 POST
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            str(response.content, encoding="utf8"),
            {"error": "Invalid request"}
        )

    def tearDown(self):
        self.client.logout()
