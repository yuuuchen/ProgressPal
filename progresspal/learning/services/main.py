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
    set_system_prompt,
    HYDE_EXPANSION_PROMPT,
    REDIRECTION_PROMPT_TEMPLATE
)
from learning.models import QuizQuestion
from accounts.models import QuizResult, QuizResultQuestion
from learning.models import Chapter,Unit
from learning.services.utils import clean_text_tutoring, clean_text_qa
from learning.services.content import get_unit
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

model = "llama-3.3-70b-versatile"

# 教材顯示
def display_materials(chapter_id, unit_id, engagement, role):
    unit = get_unit(chapter_id, unit_id)
    prompt = generate_materials(engagement, unit)    
    system_instruction = set_system_prompt(role)
    temp = 0.5 if engagement != "low" else 0.7    
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
        "extended_questions": result.get("extended_question")
    }

def validate_user_input(question):
    """
    初步過濾使用者輸入，回傳 (bool, message)
    """
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
    expanded_query = client.generate_content(model=model, messages=messages, temperature=0.3)
    return expanded_query.strip()

def generate_redirection_message(question, chapter_id, unit_id):
    """
    當 HyDE 判斷為 [IRRELEVANT] 時，生成親切的引導語句，將學生帶回教材內容。
    """
    client = get_rotational_client()
    try:
        chapter = Chapter.objects.get(chapter_number=chapter_id)
        unit = Unit.objects.get(chapter=chapter, unit_number=unit_id)
        chapter_name = chapter.title
        unit_name = unit.title
    except (Chapter.DoesNotExist, Unit.DoesNotExist):
        chapter_name = "目前的資料結構課程"
        unit_name = "當前單元"
    messages = [
        {
            "role": "system", 
            "content": "你是一位幽默、親切且專業的資管系助教，擅長用學長姐的語氣引導學生學習。"
        },
        {
            "role": "user", 
            "content": REDIRECTION_PROMPT_TEMPLATE.format(
                chapter_name=chapter_name,
                unit_name=unit_name,
                user_input=question
            )
        }
    ]
    response = client.generate_content(
        model=model, 
        messages=messages, 
        temperature=0.7 
    )    
    return response.strip()

def answer_question(question, engagement, role, chapter_id, unit_id, is_extended=False, extended_question_text=None):
    """
    1. 基礎過濾：所有提問進入系統前的第一道防線。
    2. 延伸提問：使用者點選系統生成的延伸問題。
    3. 一般提問：使用者自行輸入問題，使用 HyDE + RAG。
    """
    is_valid, error_message = validate_user_input(question)
    if not is_valid:
        return {
            "answer": error_message,
            "extended_question": "" 
        }
    if is_extended:
        # 使用者點選延伸問題，直接進入延伸處理邏輯
        return answer_extended_question(question, engagement, chapter_id, unit_id, extended_question_text, role)
    else:
        # 一般提問流程：HyDE 強化 -> RAG 檢索 -> 生成回答
        return answer_general_question(question, engagement, role, chapter_id, unit_id)

def answer_extended_question(question, engagement, chapter_id, unit_id, extended_question, role):
    """處理延伸問題的回答"""
    docs = get_unit(chapter_id, unit_id)
    prompt = generate_prompt_extended(
        engagement, question, docs, extended_question,
    )
    return respond_to_question(prompt, engagement, role)

def answer_general_question(question, engagement, role, chapter_id, unit_id):
    """處理一般提問：HyDE + RAG"""
    # 使用 HyDE 方法完整化提問
    hyde_query = expand_query_with_hyde(question, chapter_id, unit_id)
    print(f"[Debug] HyDE 擴展後的查詢語句: {hyde_query}")
    if "[IRRELEVANT]" in hyde_query:
        redirection_text = generate_redirection_message(question, chapter_id, unit_id)
        return {
            "answer": redirection_text,
            "extended_question": " "
        }
    # 執行 RAG 檢索
    docs = retrieve_docs(hyde_query, top_k=3)
    print(f"[Debug] 檢索到的文件: {docs}")

    # 呼叫 generate_prompt()
    prompt = generate_prompt(engagement, question, docs)    
    return respond_to_question(prompt, engagement, role)

def respond_to_question(prompt, engagement, role):
    system_instruction = set_system_prompt(role)
    temp = 0.5 if engagement != "low" else 0.7   
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






