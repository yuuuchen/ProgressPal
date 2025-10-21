# learning/test.py

# from django.test import TestCase
import os
import sys
import django
import json

# === Django 初始化 ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # progresspal/
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # ProgressPal/
sys.path.append(PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'progresspal.settings') 
django.setup()

from learning.services import main

def test_display_materials():
    print("\n=== 測試 display_materials ===")
    chapter = "1"
    unit = "1"
    engagement = "medium"
    try:
        result = main.display_materials(chapter, unit, engagement)
        print("教材生成成功")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print("教材生成失敗:", e)

def test_answer_question():
    print("\n=== 測試 answer_question ===")
    question = "陣列和鏈結串列的差別是什麼？"
    engagement = "medium"
    mode = main.classify_question(question)
    if mode == "relevant":
        mode = 2
    try:
        result = main.answer_question(
            mode=2,  # 模擬教材相關提問
            question=question,
            engagement=engagement,
            chapter_id="1",
            unit_id="1",
            extended_q_history={}
        )
        print("回答成功")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print("回答失敗:", e)

if __name__ == "__main__":
    print("開始測試 learning app 後端邏輯...\n")
    test_display_materials()
    test_answer_question()
    print("\n測試完成！")

