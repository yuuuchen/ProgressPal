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
    Python from learning.services.quiz import import_all_quizzes
    Python import_all_quizzes()
'''
def import_all_quizzes():
    """
    自動掃描 learning/resources/ 下的所有 CSV 檔並執行匯入
    """
    # 1. 構建 learning/resources 的絕對路徑
    resources_dir = os.path.join(settings.BASE_DIR, 'learning', 'resources')

    # 檢查目錄是否存在
    if not os.path.exists(resources_dir):
        print(f"錯誤: 找不到資源目錄 {resources_dir}")
        return

    print(f"正在掃描目錄: {resources_dir} ...")

    # 2. 遍歷目錄下的所有檔案
    csv_files = [f for f in os.listdir(resources_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print("目錄中沒有發現任何 CSV 檔案。")
        return

    total_files = len(csv_files)
    print(f"發現 {total_files} 個 CSV 檔案，準備開始匯入...")
    print("="*50)

    for index, filename in enumerate(csv_files, 1):
        file_path = os.path.join(resources_dir, filename)
        print(f"[{index}/{total_files}] 正在處理: {filename}")
        
        # 呼叫單檔匯入函式
        import_quiz_from_csv(file_path)
        print("-" * 50)

    print("所有檔案處理完成！")


def import_quiz_from_csv(file_path):
    """
    讀取單一 CSV 檔案並將題目匯入資料庫
    """
    questions_to_create = []
    success_count = 0
    error_count = 0

    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as csvfile: 
            # encoding='utf-8-sig' 可以自動處理 Excel 存檔時可能產生的 BOM 標頭
            
            reader = csv.DictReader(csvfile)
            
            # 清理欄位名稱空白
            if reader.fieldnames:
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
            else:
                print(f"檔案 {os.path.basename(file_path)} 似乎是空的或格式錯誤。")
                return

            for row_index, row in enumerate(reader, start=1):
                try:
                    # 檢查必要欄位是否存在
                    if not row.get('chapter') or not row.get('question'):
                        continue

                    # 1. 取得章節數字並查找資料庫
                    chapter_num = int(row['chapter'].strip())
                    
                    try:
                        chapter_obj = Chapter.objects.get(chapter_number=chapter_num)
                    except Chapter.DoesNotExist:
                        print(f"跳過第 {row_index} 行: 資料庫找不到 Chapter {chapter_num} (請先建立章節)")
                        error_count += 1
                        continue

                    # 2. 準備 QuizQuestion 物件
                    question = QuizQuestion(
                        chapter=chapter_obj,
                        difficulty=row['difficulty'].strip(),
                        question=row['question'].strip(),
                        option_a=row['option_A'].strip(),
                        option_b=row['option_B'].strip(),
                        option_c=row['option_C'].strip(),
                        option_d=row['option_D'].strip(),
                        answer=row['answer'].strip(),
                        explanation=row['explanation'].strip()
                    )
                    questions_to_create.append(question)
                    success_count += 1

                except KeyError as e:
                    print(f"第 {row_index} 行欄位缺失: {e}")
                    error_count += 1
                except ValueError as e:
                    print(f"第 {row_index} 行數值格式錯誤: {e}")
                    error_count += 1

        # 3. 批次寫入資料庫
        if questions_to_create:
            QuizQuestion.objects.bulk_create(questions_to_create)
            print(f"成功匯入 {len(questions_to_create)} 筆題目")
        
        if error_count > 0:
            print(f"有 {error_count} 筆資料因錯誤被略過")

    except Exception as e:
        print(f"讀取檔案時發生錯誤: {e}")