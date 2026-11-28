from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from accounts.models import QuizResult, QuizResultQuestion
from learning.models import Chapter, QuizQuestion


class InitExperimentCommandTest(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("init_experiment", stdout=out)
        return out.getvalue()

    def test_fresh_database_gets_chapter_one_with_stack_and_queue_quiz(self):
        self.run_command()
        self.assertEqual(list(Chapter.objects.values_list("chapter_number", "title")), [(1, "堆疊與佇列")])
        self.assertEqual(QuizQuestion.objects.count(), 60)
        self.assertEqual(QuizQuestion.objects.exclude(chapter__chapter_number=1).count(), 0)
        for level in ("easy", "medium", "hard"):
            self.assertEqual(QuizQuestion.objects.filter(difficulty=level).count(), 20)

    def test_second_run_keeps_existing_data(self):
        self.run_command()
        user = get_user_model().objects.create_user("P01", "p@example.com", "x")
        result = QuizResult.objects.create(user=user, chapter_code="1", score=1)
        QuizResultQuestion.objects.create(quiz_result=result, question=QuizQuestion.objects.first(),
                                          selected_answer="A", is_correct=True)
        output = self.run_command()
        self.assertIn("略過初始化", output)
        self.assertEqual(QuizQuestion.objects.count(), 60)
        self.assertEqual(QuizResultQuestion.objects.count(), 1)
