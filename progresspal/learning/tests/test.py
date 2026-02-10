import os
import sys
import django
import json

# === Django 初始化 ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'progresspal.settings')
django.setup()

from learning.services import main
from accounts.models import CustomUser
from learning.models import Chapter

def test_display_materials():
    """測試教材生成 (驗證單一延伸提問)"""
    print("\n=== 1. 測試 display_materials() ===")
    chapter_code = "1"
    unit_code = "1"
    engagement = "medium"
    role = "資訊管理系大學生"

    try:
        result = main.display_materials(chapter_code, unit_code, engagement, role)
        print("教材生成成功")
        # 驗證 extended_questions 是否為字串 (配合新的單題邏輯)
        ext_q = result.get("extended_questions")
        print(f"生成的延伸問題: {ext_q}")
        if isinstance(ext_q, list):
            print("警告: 回傳格式仍為 list，請檢查 main.py 是否已修改為單一字串。")
    except Exception as e:
        print("教材生成失敗:", e)

def test_hyde_expansion():
    """測試 HyDE 查詢擴展邏輯"""
    print("\n=== 2. 測試 expand_query_with_hyde() ===")
    question = "這個要怎麼實作？"
    chapter_code = "1"
    unit_code = "1"
    
    try:
        # 注意：此方法需在 main.py 中已實作
        expanded = main.expand_query_with_hyde(question, chapter_code, unit_code)
        print(f"原始提問: {question}")
        print(f"HyDE 擴展後: {expanded}")
        if len(expanded) > len(question):
            print("HyDE 擴展成功")
    except AttributeError:
        print("失敗: main.py 中找不到 expand_query_with_hyde 方法。")
    except Exception as e:
        print("HyDE 擴展出錯:", e)

def test_answer_question():
    """測試問答功能 (一般提問 vs 延伸提問)"""
    print("\n=== 3. 測試 answer_question() ===")
    engagement = "high"
    role = "資訊管理系大學生"
    chapter_code = "1"
    unit_code = "1"

    # A. 測試一般提問 (使用 HyDE + RAG)
    print("\n--- 測試 A: 一般提問 ---")
    q_general = "請解釋陣列的記憶體配置"
    try:
        res_gen = main.answer_question(
            question=q_general,
            engagement=engagement,
            role=role,
            chapter_id=chapter_code,
            unit_id=unit_code,
            is_extended=False
        )
        print(f"回答內容摘要: {res_gen.get('answer')[:50]}...")
        print("一般提問測試完成")
    except Exception as e:
        print("一般提問失敗:", e)

    # B. 測試延伸提問 (is_extended=True)
    print("\n--- 測試 B: 延伸提問 ---")
    q_from_user = "好，請舉個例子" # 使用者點選後可能輸入的追問或確認
    q_context = "陣列與鏈結串列在空間複雜度上有什麼具體差異？" # 模擬從 Session 抓出的延伸問題
    try:
        res_ext = main.answer_question(
            question=q_from_user,
            engagement=engagement,
            role=role,
            chapter_id=chapter_code,
            unit_id=unit_code,
            is_extended=True,
            extended_question_text=q_context
        )
        print(f"針對延伸問題的回答: {res_ext.get('answer')[:50]}...")
        print("延伸提問測試完成")
    except Exception as e:
        print("延伸提問失敗:", e)

def test_quiz_logic():
    """測試測驗邏輯"""
    print("\n=== 4. 測試測驗功能 ===")
    try:
        chapter = Chapter.objects.get(chapter_number="1")
        # 1. 測試隨機抽題
        questions = main.get_exam_questions(chapter)
        print(f"成功取出 {len(questions)} 題測驗")
        
        # 2. 模擬提交 (假設回答第一題，選選項 0)
        if questions:
            mock_user = CustomUser.objects.first() # 需確保資料庫有使用者
            user_answers = [{"question_id": questions[0].id, "selected_index": 0}]
            score, results = main.process_quiz_submission(mock_user, "1", user_answers)
            print(f"測驗批改完成，得分: {score}")
            print("測驗邏輯測試完成")
    except Exception as e:
        print("測驗測試出錯:", e)

if __name__ == "__main__":
    print("開始測試重構後的學習系統邏輯...\n")
    
    # 執行各項測試
    test_display_materials()
    test_hyde_expansion()
    test_answer_question()
    test_quiz_logic()
    
    print("\n測試程序執行完畢！")