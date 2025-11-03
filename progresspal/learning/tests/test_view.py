# learning/tests/test_views.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from learning.models import Chapter, Unit

class LearningViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='testuser',
            password='12345',
            role='student',
            emotions=['neutral', 'happy']  # 模擬情緒序列
        )

        # 模擬章節與單元
        self.chapter = Chapter.objects.create(chapter_number="1", title="陣列")
        self.unit = Unit.objects.create(unit_number="1", chapter=self.chapter, title="陣列介紹")

    def test_generate_materials_view(self):
        """測試教材生成頁面"""
        self.client.login(username='testuser', password='12345')
        response = self.client.get(f'/learning/{self.chapter.chapter_number}/{self.unit.unit_number}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('teaching', response.content.decode())

    def test_answer_question_view(self):
        """測試教材問答 AJAX"""
        self.client.login(username='testuser', password='12345')

        payload = {
            "user_question": "陣列和鏈結串列的差別是什麼？",
            "question_choice": "direct"
        }

        response = self.client.post(
            f'/learning/{self.chapter.chapter_number}/{self.unit.unit_number}/answer/',
            data=payload,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('answer', data)
