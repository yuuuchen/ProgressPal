import json
from unittest.mock import patch, PropertyMock, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from learning.models import Chapter, Unit, QuizQuestion
from accounts.models import QuestionLog

User = get_user_model()

class LearningViewsIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_mis",
            email="test_mis@gmail.com",
            password="MISMIS2486",
            role="student"
        )
        self.client.login(username="test_mis", password="MISMIS2486")

        # 建立測試資料：注意 chapter_number 是字串還是整數，需對齊 Model 定義
        self.chapter = Chapter.objects.create(
            chapter_number="1", title="陣列(Array)"
        )
        self.unit = Unit.objects.create(
            unit_number="1", title="陣列概論", chapter=self.chapter
        )

    @patch("learning.views.main.display_materials")
    @patch("learning.views.compute_engagement")
    @patch("accounts.models.CustomUser.recent_emotion_history", new_callable=PropertyMock)
    def test_generate_materials_view(self, mock_history, mock_engagement, mock_display):
        mock_history.return_value = ['喜悅']
        mock_engagement.return_value = "high"
        mock_display.return_value = {"teaching": "內容", "example": "範例", "summary": "摘要", "extended_questions": "Q1"}

        # 對齊 urls.py 中的 name='learning'
        # 且 urls.py 定義為 <int:chapter_code>，建議傳入整數
        url = reverse("learning", args=[1, 1]) 
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        print("\ngenerate_materials_view 測試成功")

    @patch("learning.views.main.answer_question")
    @patch("learning.views.compute_engagement")
    @patch("accounts.models.CustomUser.recent_emotion_history", new_callable=PropertyMock)
    def test_answer_question_view(self, mock_history, mock_engagement, mock_answer):
        mock_history.return_value = ['投入']
        mock_engagement.return_value = "medium"
        mock_answer.return_value = {"answer": "AI回答", "extended_question": "Q2"}

        # 對齊 urls.py 中的 name='chat-api'
        url = reverse("chat-api", args=[1, 1])
        data = {"question_choice": "direct", "user_question": "測試提問"}

        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        print("answer_question_view 測試成功")

    @patch("learning.views.main.get_exam_questions")
    def test_chapter_quiz_api(self, mock_get_questions):
        mock_get_questions.return_value = []
        # 對齊 urls.py 中的 name='quiz-api'
        url = reverse("quiz-api", args=[1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        print("chapter_quiz_api 測試成功")

    @patch("learning.views.main.process_quiz_submission")
    def test_check_answers(self, mock_process):
        mock_process.return_value = (100, [])
        # 對齊 urls.py 中的 name='quiz-check-api'
        url = reverse("quiz-check-api", args=[1])
        data = {"answers": []}
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        print("check_answers 測試成功")