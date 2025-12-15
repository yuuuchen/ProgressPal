# learning/services/main.py
'''
主要服務模組，整合問答、教材生成與測驗功能
'''
import os, re, textwrap, time, json,random
from dotenv import load_dotenv

from google import genai
from google.genai import types
from google.api_core import exceptions

from django.conf import settings
from learning.services.prompt import (
    generate_prompt,
    generate_materials,
    generate_prompt_extended,
    set_system_prompt
)
from learning.models import QuizQuestion
from learning.services.content import get_unit, get_chapter
from learning.services.utils import clean_text_tutoring, clean_text_qa
from rag.services.rag import retrieve_docs

class RotationalGeminiClient:
    """
    設計一個包裝過的 Client，用來自動輪替 API Keys。模仿官方 genai.Client 的呼叫結構： client.models.generate_content(...)
    """
    def __init__(self):
        # 從 settings 取得所有的 Keys
        self.api_keys = settings.GOOGLE_API_KEYS
        # 初始化 models 屬性，讓外部可以用 client.models 呼叫
        self.models = self._ModelsWrapper(self.api_keys)

    class _ModelsWrapper:
        def __init__(self, api_keys):
            self.api_keys = api_keys
        def generate_content(self, **kwargs):
            """
            這裡接收原本 generate_content 的所有參數 (model, config, contents...)
            並在遇到 Rate Limit 時自動換 Key。
            """
            last_error = None           
            # 遍歷所有 Key
            for index, key in enumerate(self.api_keys):
                try:
                    # 使用當前的 Key 建立真正的 Client
                    real_client = genai.Client(api_key=key)                    
                    # 執行生成 (將參數透傳給真正的 Client)
                    response = real_client.models.generate_content(**kwargs)                   
                    # 成功則回傳
                    return response
                except Exception as e:
                    error_msg = str(e)
                    # 判斷是否為流量限制相關錯誤 (429, Quota, ResourceExhausted)
                    if ("429" in error_msg or "ResourceExhausted" in error_msg or "403" in error_msg or "400" in error_msg or "API_KEY_INVALID" in error_msg):
                        print(f"[警告] Key #{index+1} 失效或流量耗盡 (Error: {error_msg[:50]}...)，切換下一個 Key 重試...")
                        last_error = e
                        continue # 換下一個 Key
                    else:
                        # 如果是參數錯誤或其他問題，直接報錯，不要換 Key
                        raise e           
            # 如果跑完所有 Key 都失敗
            raise RuntimeError("所有 API Key 的流量都已耗盡。") from last_error
def get_rotational_client():
    return RotationalGeminiClient()

model = "gemini-2.5-flash"

# 問題分類
CLASSIFICATION_PROMPT = """
你是一位智慧助教，專精於資料結構教學。
這是一個對話情境，你要根據上下文來判斷學生提問的類別。

類別定義：
- relevant(與教材相關)：例如「什麼是陣列？」「堆疊如何運作？」
- demand(學生需求相關)：例如「可以幫我整理這章節的考試重點嗎？」「能否推薦這單元的練習題？」「請講解更知識面」「能再用更簡單的比喻嗎」
- irrelevant(不相關)：例如「你喜歡吃什麼？」「今天幾點下課？」

若類別為 relevant，請同時抽取提問中的**關鍵字**，以利教材檢索。關鍵字請用單詞或短語，避免長句。
若類別不是 relevant，請輸出空陣列。

問題：{question}

輸出請用 JSON 格式，例如:
{{"category": "clarification", "keywords": []}}
"""
def classify_question(question: str) -> dict:
    client = get_rotational_client()
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=CLASSIFICATION_PROMPT + "\n\n學生提問：" + question)]
            )
        ]
    )
    text = response.text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError(f"模型輸出不是 JSON 格式: {text}")

    json_str = match.group(0)
    return json.loads(json_str)

# 參數與系統設定
def get_gen_config(engagement,role):
    """依照學生參與度設定 temperature"""
    temperature = 0.3 if engagement != "low" else 0.5
    SYSTEM_PROMPT = set_system_prompt(role)
    return types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=temperature)

# 教材顯示
def display_materials(chapter_id, unit_id, engagement, role):
    unit = get_unit(chapter_id, unit_id)
    prompt = generate_materials(engagement, unit)
    gen_config = get_gen_config(engagement, role)
    client = get_rotational_client()
    resp = client.models.generate_content(
        model=model,
        config=gen_config,
        contents=[{"role": "user", "parts": [{"text": prompt}]}]
    )
    result = clean_text_tutoring(resp.text)
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
    docs = get_chapter(chapter_id)
    prompt = generate_prompt_extended(
        engagement, question, docs,extended_question,
    )
    return respond_to_question(prompt, engagement, role)

def answer_relevant_question(question, engagement, role):
    analysis = classify_question(question)
    if analysis["category"] != "relevant":
        return {"error": "這個問題與教材無關"}
    docs = retrieve_docs(analysis, top_k=5)
    prompt = generate_prompt(engagement, question, docs)
    return respond_to_question(prompt, engagement, role)

def answer_demand_question(question, engagement, unit_id, role):
    analysis = classify_question(question)
    if analysis["category"] != "demand":
        return {"error": "這不是學習需求類問題"}
    docs = get_unit(unit_id)
    prompt = generate_prompt(engagement, question, docs)
    return respond_to_question(prompt, engagement, role)

def respond_to_question(prompt, engagement, role):
    gen_config = get_gen_config(engagement, role)
    client = get_rotational_client()
    resp = client.models.generate_content(
        model=model,
        config=gen_config,
        contents=[{"role": "user", "parts": [{"text": prompt}]}]
    )
    result = clean_text_qa(resp.text)
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






