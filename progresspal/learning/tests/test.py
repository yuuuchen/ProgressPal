import os
import sys
import django
import json

# === Django 初始化 ===
# 假設本檔案位於 learning/tests/test.py，進入專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

print(f"專案根目錄設為: {BASE_DIR}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'progresspal.settings')
django.setup()

from learning.services import main

def test_display_materials():
    """測試教材生成"""
    print("\n=== 測試 display_materials() ===")
    chapter_code = "1"
    unit_code = "1"
    engagement = "medium"
    role = "資訊管理系大學生"

    try:
        result = main.display_materials(chapter_code, unit_code, engagement, role)
        print("教材生成成功")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print("教材生成失敗:", e)

def test_answer_question():
    """測試問答功能"""
    print("\n=== 測試 answer_question() ===")
    question = "陣列和鏈結串列的差別是什麼？"
    engagement = "medium"
    role = "資訊管理系大學生"
    chapter_code = "1"
    unit_code = "1"

    try:
        # 先分類問題
        classification = main.classify_question(question)
        print("問題分類結果:", classification)

        # 決定模式（依據分類結果）
        category = classification.get("category")
        if category == "relevant":
            mode = 2
        elif category == "demand":
            mode = 3
        else:
            print("問題與教材無關，跳過測試。")
            return

        # 模擬延伸問題暫存
        extended_q_history = "陣列與鏈結串列有何不同"

        # 呼叫回答邏輯
        result = main.answer_question(
            mode=mode,
            question=question,
            engagement=engagement,
            role=role,
            chapter_id=chapter_code,
            unit_id=unit_code,
            extended_q_history=extended_q_history
        )

        print("問答生成成功")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print("問答生成失敗:", e)

if __name__ == "__main__":
    print("開始測試 learning app 後端邏輯...\n")
    test_display_materials()
    test_answer_question()
    print("\n測試完成！")
