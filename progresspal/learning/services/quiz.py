import csv
import os
from django.core.exceptions import ObjectDoesNotExist
import glob
from django.conf import settings
from django.db import transaction
from learning.models import Chapter, QuizQuestion 

# ==========================================
# 使用範例 (如何在 Django Shell 中執行)
# ==========================================
'''
1. 在終端機 (Terminal) 輸入：python manage.py shell
2. 進入 Shell 後，輸入以下指令執行：
    from learning.services.quiz import import_all_quizzes
    import_all_quizzes()
'''

def import_all_quizzes():
    """
    自動掃描 learning/resources/ 下的所有 CSV 檔並執行匯入
    """
    resources_dir = os.path.join(settings.BASE_DIR, 'learning', 'resources')

    if not os.path.exists(resources_dir):
        print(f"錯誤: 找不到資源目錄 {resources_dir}")
        return

    csv_files = [f for f in os.listdir(resources_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print("目錄中沒有發現任何 CSV 檔案。")
        return

    print(f"發現 {len(csv_files)} 個 CSV 檔案，準備開始匯入...")
    print("="*50)

    for filename in csv_files:
        file_path = os.path.join(resources_dir, filename)
        print(f"正在處理檔案: {filename}")
        import_quiz_from_csv(file_path)
        print("-" * 50)

def import_quiz_from_csv(file_path):
    """
    讀取單一 CSV 檔案並匯入資料庫 (防止重複儲存版)
    """
    if os.path.getsize(file_path) == 0:
        print(f"失敗: 檔案是空的 (0 bytes)。")
        return

    questions_to_create = []
    success_count = 0
    skip_count = 0  # 新增跳過計數
    error_count = 0

    encodings_to_try = ['utf-8-sig', 'utf-8', 'big5', 'cp950']
    decoded_file = None
    used_encoding = None

    for enc in encodings_to_try:
        try:
            f = open(file_path, mode='r', encoding=enc)
            f.readline()
            f.seek(0)
            decoded_file = f
            used_encoding = enc
            break
        except UnicodeDecodeError:
            f.close()
            continue
    
    if not decoded_file:
        print(f"失敗: 無法辨識檔案編碼。")
        return

    print(f"使用編碼: {used_encoding}")

    try:
        with decoded_file as csvfile:
            reader = csv.DictReader(csvfile)
            
            if not reader.fieldnames:
                print(f"失敗: 讀取不到標題。")
                return
            
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row_index, row in enumerate(reader, start=1):
                try:
                    if not row.get('chapter') or not row.get('question'):
                        continue

                    # 1. 取得章節
                    try:
                        chapter_num = int(row['chapter'].strip())
                        chapter_obj = Chapter.objects.get(chapter_number=chapter_num)
                    except (ValueError, Chapter.DoesNotExist):
                        print(f"第 {row_index} 行跳過: 章節錯誤")
                        error_count += 1
                        continue

                    # 2. 【關鍵修改】檢查題目是否已存在
                    question_text = row.get('question', '').strip()
                    if QuizQuestion.objects.filter(chapter=chapter_obj, question=question_text).exists():
                        # print(f" 第 {row_index} 行跳過: 題目已存在") # 如果覺得訊息太多可以註解掉這行
                        skip_count += 1
                        continue

                    # 3. 準備建立物件
                    question = QuizQuestion(
                        chapter=chapter_obj,
                        difficulty=row.get('difficulty', 'easy').strip(),
                        question=question_text,
                        option_a=row.get('option_A', '').strip(),
                        option_b=row.get('option_B', '').strip(),
                        option_c=row.get('option_C', '').strip(),
                        option_d=row.get('option_D', '').strip(),
                        answer=row.get('answer', '').strip(),
                        explanation=row.get('explanation', '').strip()
                    )
                    questions_to_create.append(question)
                    success_count += 1

                except Exception as e:
                    print(f"第 {row_index} 行錯誤: {e}")
                    error_count += 1

        # 4. 寫入資料庫
        if questions_to_create:
            QuizQuestion.objects.bulk_create(questions_to_create)
            print(f"成功新增 {success_count} 筆題目")
        else:
            print(f"沒有需要新增的題目")

        if skip_count > 0:
            print(f"跳過 {skip_count} 筆重複的題目")
        
        if error_count > 0:
            print(f"發生 {error_count} 筆錯誤")

    except Exception as e:
        print(f"錯誤: {e}")
    finally:
        if decoded_file and not decoded_file.closed:
            decoded_file.close()