# learning/services/main.py
'''
主要服務模組，整合問答、教材生成與測驗功能
'''
import os, re, textwrap, time, json,random
from dotenv import load_dotenv

from groq import Groq

from django.db import transaction
from django.conf import settings
from learning.services.prompt import (
    generate_prompt,
    generate_materials,
    generate_prompt_extended,
    set_system_prompt
)
from learning.models import QuizQuestion
from accounts.models import QuizResult, QuizResultQuestion
from learning.services.content import get_unit, get_chapter
from learning.services.utils import clean_text_tutoring, clean_text_qa
from rag.services.rag import retrieve_docs
from . import utils

class RotationalGroqClient:
    """自動輪替 Groq API Keys 的 Client"""
    def __init__(self):
        self.api_keys = settings.GROQ_API_KEYS

    def generate_content(self, model, messages, temperature=0.3):
        """
        模擬 Groq 的 chat.completions.create 並加入 Key 輪替邏輯
        """
        last_error = None           
        for index, key in enumerate(self.api_keys):
            try:
                clean_key = str(key).strip().replace('"', '').replace("'", "")
                real_client = Groq(api_key=clean_key)                    
                response = real_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                )                   
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                print(f"[除錯] Groq Key #{index+1} 發生錯誤: {error_msg}")
                # 針對 Groq 的 Rate Limit (429) 或授權問題進行切換
                if "429" in error_msg or "rate_limit" in error_msg or "401" in error_msg:
                    print(f"[警告] Groq Key #{index+1} 失效或流量耗盡，切換下一個 Key...")
                    last_error = e
                    continue 
                else:
                    raise e           
        raise RuntimeError("所有 Groq API Key 的流量都已耗盡。") from last_error

def get_rotational_client():
    return RotationalGroqClient()

# 設定為指定的 Llama 3.3 模型
model = "llama-3.3-70b-versatile"

# 問題分類
CLASSIFICATION_PROMPT = """
你是一位智慧助教，專精於資料結構教學。
這是一個對話情境，你要根據上下文來判斷學生提問的類別。

類別定義：
- relevant(與教材相關)：例如「什麼是陣列？」「堆疊如何運作？」
- demand(學生需求相關)：例如「可以幫我整理這章節的考試重點嗎？」「能否推薦這單元的練習題？」「請講解更知識面」「能再用更簡單的比喻嗎」
- irrelevant(不相關)：例如「你喜歡吃什麼？」「今天幾點下課？」

問題：{question}

輸出請用 JSON 格式，例如:
{ "category": "relevant" }
"""
def classify_question(question: str) -> dict:
    client = get_rotational_client()
    messages = [
        {"role": "system", "content": "你是一位智慧助教，專精於資料結構教學。"},
        {"role": "user", "content": CLASSIFICATION_PROMPT + "\n\n學生提問：" + question}
    ]    
    response_text = client.generate_content(
        model=model,
        messages=messages,
        temperature=0.1 
    )    
    text = response_text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"模型輸出不是 JSON 格式: {text}")
    return json.loads(match.group(0))

# 教材顯示
def display_materials(chapter_id, unit_id, engagement, role):
    unit = get_unit(chapter_id, unit_id)
    prompt = generate_materials(engagement, unit)    
    # 取得系統提示詞與溫度
    system_instruction = set_system_prompt(role)
    temp = 0.3 if engagement != "low" else 0.5    
    client = get_rotational_client()
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]    
    resp_text = client.generate_content(model=model, messages=messages, temperature=temp)
    result = clean_text_tutoring(resp_text)    
    return {
        "teaching": result.get("teaching"),
        "example": result.get("example"),
        "summary": result.get("summary"),
        "extended_questions": result.get("extended_question")
    }

# 問答回應
def answer_question(mode, question, engagement, role, chapter_id=None, unit_id=None, extended_question=None):
    """
    mode:
      1: 回應延伸問題
      2: 直接提問(與教材相關)
      3: 直接提問(學習需求相關)
    """
    if mode == 1:
        return answer_extended_question(question, engagement, chapter_id, unit_id, extended_question, role)
    elif mode == 2:
        return answer_relevant_question(question, engagement, role)
    elif mode == 3:
        return answer_demand_question(question, engagement, unit_id, role)
    else:
        return {"error": "Invalid mode"}

def answer_extended_question(question, engagement, chapter_id, unit_id, extended_question, role):
    docs = get_unit(chapter_id, unit_id)
    prompt = generate_prompt_extended(
        engagement, question, docs,extended_question,
    )
    return respond_to_question(prompt, engagement, role)

def answer_relevant_question(question, engagement, role):
    analysis = classify_question(question)
    if analysis["category"] != "relevant":
        return {"error": "這個問題與教材無關"}
    docs = retrieve_docs(question, top_k=3)
    prompt = generate_prompt(engagement, question, docs)
    return respond_to_question(prompt, engagement, role)

def answer_demand_question(question, engagement, chapter_id, unit_id, role):
    analysis = classify_question(question)
    if analysis["category"] != "demand":
        return {"error": "這不是學習需求類問題"}
    docs = get_unit(chapter_id,unit_id)
    prompt = generate_prompt(engagement, question, docs)
    return respond_to_question(prompt, engagement, role)

def respond_to_question(prompt, engagement, role):
    system_instruction = set_system_prompt(role)
    temp = 0.3 if engagement != "low" else 0.5    
    client = get_rotational_client()
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]    
    resp_text = client.generate_content(model=model, messages=messages, temperature=temp)
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






