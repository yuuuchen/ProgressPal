# learning/services/main.py
'''
主要服務模組，整合問答、教材生成與測驗功能
'''
import os, re, textwrap, time, json,random

from django.db import transaction
from learning.services.llm_model import (model_qa,model_materials,get_rotational_client)
from learning.services.prompt import (
    generate_prompt,
    generate_materials,
    generate_prompt_extended,
    set_system_prompt,
    HYDE_EXPANSION_PROMPT,
    REDIRECTION_PROMPT,
)
from learning.models import QuizQuestion
from accounts.models import QuizResult, QuizResultQuestion
from learning.models import Chapter,Unit
from learning.services.utils import clean_text_tutoring, clean_text_qa
from learning.services.content import get_unit
from rag.services.rag import retrieve_docs
from . import utils

def display_materials(chapter_id, unit_id, engagement, role):
    """教材顯示"""
    unit = get_unit(chapter_id, unit_id)
    prompt = generate_materials(role, engagement, unit)    
    system_instruction = set_system_prompt(role)
    client = get_rotational_client()
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]    
    resp_text = client.generate_materials_content(model=model_materials, messages=messages)
    result = clean_text_tutoring(resp_text)  
    print(f"[Debug] 教材生成原始回應: {resp_text}")  
    return {
        "guide": result.get("guide"),
        "core": result.get("core"),
        "example": result.get("example"),
        "extended_question": result.get("extended_question")
    }

def validate_user_input(question):
    """初步過濾使用者輸入，回傳 (bool, message)"""
    # 去除前後空白
    text = question.strip()
    # 1. 檢查是否為空
    if not text:
        return False, "輸入內容不能為空喔！請試著問我關於資料結構的問題。"
    # 2. 檢查字數是否過短 (至少要 2 個字，可依需求調整)
    if len(text) < 2:
        return False, "你的提問太簡短了，助教可能無法理解，再多寫一點點吧！"
    # 3. 檢查是否純粹為標點符號或特殊字元
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', text):
        return False, "請輸入有意義的文字，不要只傳標點符號或符號喔！"
    # 4. 檢查是否有過度重複的內容 (例如: aaaaaa, 哈哈哈...)
    if re.search(r'(.)\1{4,}', text):
        return False, "偵測到重複性過高的內容，請輸入具體的提問。"
    return True, ""

def expand_query_with_hyde(question, chapter_id, unit_id):
    """利用 HyDE 方法，結合教材上下文將提問轉換成更豐富的檢索詞"""
    client = get_rotational_client()
    
    # 取得名稱以提供上下文
    chapter = Chapter.objects.get(chapter_number=chapter_id)
    unit = Unit.objects.get(chapter=chapter, unit_number=unit_id)
    chapter_name = chapter.title
    unit_name = unit.title
    # Debug 用：確認傳入的名稱是否有意義
    # print(f"[Debug] HyDE Context: Chapter={chapter_name}, Unit={unit_name}")

    messages = [
        {"role": "system", "content": "你是一個查詢優化專家，擅長將模糊問題轉化為精準的技術檢索詞。"},
        {"role": "user", "content": HYDE_EXPANSION_PROMPT.format(
            chapter_name=chapter_name,
            unit_name=unit_name,
            question=question
        )}
    ]    
    expanded_query = client.generate_qa_content(model=model_qa, messages=messages, temperature=0.3)
    return expanded_query.strip()

def generate_redirection_message(user_input, chapter_id, unit_id, error_msg=None):
    """
    - 若有 error_msg：針對輸入錯誤（亂碼、太短等）進行優化回應。
    - 若無 error_msg：針對離題（HyDE 判定 IRRELEVANT）進行引導。
    """
    client = get_rotational_client()
    chapter = Chapter.objects.get(chapter_number=chapter_id)
    unit = Unit.objects.get(chapter=chapter, unit_number=unit_id)
    docs = get_unit(chapter_id, unit_id)
    # 準備對話訊息
    messages = [
        {"role": "system", "content": "你是一位親切的資管系助教，擅長鼓勵學生並引導他們回到學習主軸。"},
        {"role": "user", "content": REDIRECTION_PROMPT.format(
            chapter_name=chapter.title,
            unit_name=unit.title,
            user_input=user_input,
            error_msg=error_msg if error_msg else "這是一個與課程無關的話題",
            docs=docs  # 補上 Prompt 裡需要的 docs 變數
        )}
    ]        
    try:
        # 呼叫 LLM (依據你的 client API 可能回傳字串或物件，此處假設與原版行為相同)
        raw_response = client.generate_qa_content(model=model_qa, messages=messages, temperature=0.7)
        
        # 確保轉為字串格式
        raw_text = raw_response if isinstance(raw_response, str) else str(raw_response)
        
        # 呼叫 clean_text_qa 進行統一格式解析
        result = clean_text_qa(raw_text)
        
        # 如果模型沒有照格式輸出，替換為預設回覆
        if result["answer"] == "（模型未輸出回答）":
            result["answer"] = error_msg if error_msg else "我們還是先回來聊聊資料結構吧！"
        if result["extended_question"] == "（模型未輸出回答）":
            result["extended_question"] = f"你知道 {unit.title} 最重要的概念是什麼嗎？"        
        return result

    except Exception as e:
        # 錯誤處理 (API 錯誤或其他異常)：回傳預設的安全回應
        return {
            "answer": error_msg if error_msg else "我們還是先回來聊聊資料結構吧！",
            "extended_question": f"你知道 {unit.title} 最重要的概念是什麼嗎？"
        }

def answer_question(question, engagement, role, chapter_id, unit_id, is_extended=False, extended_question_text=None):
    """
    1. 基礎過濾：所有提問進入系統前的第一道防線。
    2. 延伸提問：使用者點選系統生成的延伸問題。
    3. 一般提問：使用者自行輸入問題，使用 HyDE + RAG。
    """
    is_valid, error_message = validate_user_input(question)
    if not is_valid:
        return generate_redirection_message(
            user_input=question, 
            chapter_id=chapter_id, 
            unit_id=unit_id, 
            error_msg=error_message
        )
    if is_extended:
        # 使用者點選延伸問題，直接進入延伸處理邏輯
        return answer_extended_question(question, engagement, chapter_id, unit_id, extended_question_text, role)
    else:
        # 使用 HyDE 方法完整化提問
        hyde_query = expand_query_with_hyde(question, chapter_id, unit_id)
        # print(f"[Debug] HyDE 擴展後的查詢語句: {hyde_query}")
        if "[IRRELEVANT]" in hyde_query:
            return generate_redirection_message(question, chapter_id, unit_id, error_msg=None)
        # 執行 RAG 檢索
        docs = retrieve_docs(hyde_query, top_k=3)
        # print(f"[Debug] 檢索到的文件: {docs}")

        prompt = generate_prompt(engagement, question, docs)    
        return respond_to_question(prompt, engagement, role)

def answer_extended_question(question, engagement, chapter_id, unit_id, extended_question, role):
    """處理延伸問題的回答"""
    docs = get_unit(chapter_id, unit_id)
    prompt = generate_prompt_extended(
        engagement, question, docs, extended_question,
    )
    return respond_to_question(prompt, engagement, role)
    
def respond_to_question(prompt, engagement, role):
    system_instruction = set_system_prompt(role)
    temp = 0.5 if engagement != "low" else 0.7   
    client = get_rotational_client()
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]    
    resp_text = client.generate_qa_content(model=model_qa, messages=messages, temperature=temp)
    result = clean_text_qa(resp_text)    
    return {
        "answer": result.get("answer"),
        "extended_question": result.get("extended_question")
    }

def get_exam_questions(chapter):
    """
    根據指定章節回傳隨機 10 題（簡單 4、中等 3、困難 3）。若題庫不足，會自動縮減。
    """
    # 讀取題庫
    difficulty_map = {
        "easy": 4,
        "medium": 3,
        "hard": 3,
    }
    selected = []
    for level, required_num in difficulty_map.items():
        qs = list(QuizQuestion.objects.filter(chapter=chapter, difficulty=level))
        count = min(required_num, len(qs))
        if count > 0:
            selected.extend(random.sample(qs, count))
    # 打亂
    random.shuffle(selected)
    return selected

def process_quiz_submission(user, chapter_code, user_answers_list):
    """
    處理測驗提交：計算分數、生成詳細結果並寫入資料庫。回傳: (score, results) tuple
    """
    if not user_answers_list:
        return 0, []
    # 1. 取得所有題目資料
    question_ids = [item.get('question_id') for item in user_answers_list]
    questions = QuizQuestion.objects.filter(id__in=question_ids)
    question_map = {q.id: q for q in questions}
    results = []
    score = 0
    details_to_create = []
    # 2. 核心邏輯：比對答案與計算分數
    for item in user_answers_list:
        q_id = item.get('question_id')
        user_selected = item.get('selected_index')        
        question_obj = question_map.get(q_id)
        if not question_obj:
            continue            
        is_correct = (user_selected == question_obj.answer)       
        if is_correct:
            score += 1
        # 準備回傳給前端的資料結構
        results.append({
            "question_id": question_obj.id,
            "question": question_obj.question,
            "options": [
                utils.to_markdown(question_obj.option_a),
                utils.to_markdown(question_obj.option_b),
                utils.to_markdown(question_obj.option_c),
                utils.to_markdown(question_obj.option_d),
            ],
            "user_answer": user_selected,
            "answer": question_obj.answer,
            "explanation": utils.to_markdown(question_obj.explanation),
            "is_correct": is_correct,
        })
        # 準備寫入資料庫的明細物件
        details_to_create.append({
            "question": question_obj,
            "user_answer": user_selected,
            "is_correct": is_correct
        })
    # 3. 資料庫寫入 (使用 transaction 確保資料一致性)
    with transaction.atomic():
        # 建立測驗紀錄
        quiz_result = QuizResult.objects.create(
            user=user,
            chapter_code=chapter_code,
            score=score,
        )
        # 建立測驗明細紀錄
        QuizResultQuestion.objects.bulk_create([
            QuizResultQuestion(
                quiz_result=quiz_result,
                question=d['question'],
                selected_answer=d['user_answer'],
                is_correct=d['is_correct'],
            )
            for d in details_to_create
        ])
    return score, results






