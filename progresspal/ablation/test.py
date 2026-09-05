# -*- coding: utf-8 -*-
import os
import sys
import time
import csv
import django

# ==========================================
# 1. 環境與路徑設定 (適應 ablation 資料夾)
# ==========================================
# 取得目前 run_ablation.py 所在的 ablation 目錄
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 取得專案根目錄 (即 ablation 的上一層)
BASE_DIR = os.path.dirname(CURRENT_DIR)

# 將專案根目錄加入 sys.path，這樣才能順利 import Django app
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 設定 Django 環境變數 (⚠️ 請將 your_project_name 替換成你的 Django 專案名稱)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'progresspal.settings') 
django.setup()
# ==========================================
# 2. 匯入最新系統模組
# ==========================================
from learning.services.llm_model import get_rotational_client, model_qa
from rag.services.rag import retrieve_docs
from learning.services.prompt import set_system_prompt, generate_prompt

def get_group_configuration(group_name, question, bg_level, eng_level):
    """
    依照消融實驗的四個組別，動態配置 System Prompt 與 User Prompt
    """
    sys_prompt = ""
    user_prompt = ""
    retrieved_context = ""
    materials_list = []

    # 1. 處理先備知識的映射 
    knowledge_level = 'high_prior_student' if bg_level.upper() == 'HPK' else 'low_prior_student'
    engagement = eng_level.lower()

    # 2. 處理 RAG 檢索 (只有組別 2 與 4 需要去 Chroma 撈資料)
    if group_name in ["2_RAG_Only", "4_Full_System"]:
        docs = retrieve_docs(question, top_k=3)
        if docs:
            materials_list = [doc.page_content for doc in docs]
            retrieved_context = "\n\n".join(materials_list)
        else:
            materials_list = ["無相關教材。"]
            retrieved_context = "無相關教材。"

    # 3. 根據四個消融組別，配置對應的指令
    if group_name == "1_General_LLM":
        # 全無：一般通用設定，不給 RAG，不給情緒 Prompt
        sys_prompt = """
        你是一位資料結構助教，請清晰地回答學生的問題。總字數必須 ≤ 350 字。
        請務必嚴格依照以下結構與標題輸出：
        ### 回答問題
        （在此回答學生的問題）
        ### 引導提問
        （請針對剛剛的內容，提出一個延伸問題）
        ### 提示
        （請給予學生回答該問題的簡單提示，40字內）
        """
        user_prompt = question
        
    elif group_name == "2_RAG_Only":
        # 只有 RAG：給予檢索教材，但完全「不使用」 prompt.py 的情緒渲染
        sys_prompt = """
        你是一位資料結構助教，請「嚴格根據以下參考教材」回答問題，不要超出教材範圍。總字數必須 ≤ 350 字。
        請務必嚴格依照以下結構與標題輸出：
        ### 回答問題
        （在此回答學生的問題）
        ### 引導提問
        （請針對剛剛的內容，提出一個延伸問題）
        ### 提示
        （請給予學生回答該問題的簡單提示，40字內）
        """
        user_prompt = f"問題：{question}\n\n[參考教材]\n{retrieved_context}"
        
    elif group_name == "3_Prompt_Only":
        # 只有情緒 Prompt：呼叫 prompt.py，但 materials 餵空陣列 [] (無 RAG)
        sys_prompt = set_system_prompt(knowledge_level=knowledge_level)
        user_prompt = generate_prompt(engagement=engagement, question=question, materials=[])
        
    elif group_name == "4_Full_System":
        # 全有 (ProgressPal 完整系統)：呼叫 prompt.py，並且把撈到的 RAG materials 餵進去
        sys_prompt = set_system_prompt(knowledge_level=knowledge_level)
        user_prompt = generate_prompt(engagement=engagement, question=question, materials=materials_list)

    return sys_prompt, user_prompt, retrieved_context

def main():
    print("🚀 準備開始執行消融實驗 (支援 Groq 架構)...")
    
    # 動態綁定檔案路徑到 ablation 資料夾下
    input_csv = os.path.join(CURRENT_DIR, "ablation_experiment_dataset.csv")
    output_csv = os.path.join(CURRENT_DIR, "ablation_experiment_results.csv")
    
    if not os.path.exists(input_csv):
        print(f"❌ 發生錯誤：在 {CURRENT_DIR} 找不到測試資料集 ablation_experiment_dataset.csv")
        return

    test_data = []
    with open(input_csv, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_data.append(row)
    
    # 呼叫新版的 Groq Rotational Client 與 模型名稱
    client = get_rotational_client()
    
    groups = ["1_General_LLM", "2_RAG_Only", "3_Prompt_Only", "4_Full_System"]
    results_list = []

    total_tasks = len(test_data) * len(groups)
    task_count = 0

    # 開始批次生成
    for row in test_data:
        q_id = row['question_id']
        q_type = row['question_type']
        q_style = row['question_style']
        q_text = row['question']
        bg_level = row['student_background']
        eng_level = row['student_engagement']

        for group in groups:
            task_count += 1
            print(f"🔄 進度 {task_count}/{total_tasks} | 題目 ID: {q_id} | 組別: {group}")
            
            # 取得該組別專屬的 Prompt 配置
            sys_prompt, user_prompt, retrieved_context = get_group_configuration(
                group, q_text, bg_level, eng_level
            )

            # 將 Prompt 封裝為 Groq 支援的 messages 格式
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 呼叫 Groq API 生成 (對齊 llm_model.py 的用法)
            try:
                llm_reply = client.generate_qa_content(
                    model=model_qa, 
                    messages=messages, 
                    temperature=0.7
                )
            except Exception as e:
                print(f"❌ API 發生錯誤 (題目 {q_id}, {group}): {e}")
                llm_reply = f"ERROR: {str(e)}"

            # 寫入包含分析所需要的所有維度
            results_list.append({
                "question_id": q_id,
                "question_type": q_type,
                "question_style": q_style,
                "student_background": bg_level,
                "student_engagement": eng_level,
                "question": q_text,
                "system_group": group,
                "retrieved_context": retrieved_context,
                "system_prompt": sys_prompt,
                "user_prompt": user_prompt, 
                "llm_response": llm_reply
            })
            
            # 稍等 2 秒，防範 API 流量警告
            time.sleep(2) 

    # 定義輸出的欄位順序 (即 dictionary 的 keys)
    fieldnames = [
        "question_id", "question_type", "question_style", 
        "student_background", "student_engagement", "question", 
        "system_group", "retrieved_context", "system_prompt", 
        "user_prompt", "llm_response"
    ]
    
    with open(output_csv, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()      # 寫入第一行標題
        writer.writerows(results_list) # 寫入所有資料列
        
    print(f"🎉 實驗執行完畢！共生成 {len(results_list)} 筆資料，已存檔為 {output_csv}")

if __name__ == "__main__":
    main()