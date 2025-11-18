# learning/services/main.py
import os, re, textwrap, time, json
from dotenv import load_dotenv
from google import genai
from google.genai import types

from learning.services.prompt import (
    generate_prompt,
    generate_materials,
    generate_prompt_extended,
    set_system_prompt
)
from learning.services.content import get_unit, get_chapter
from learning.services.utils import clean_text_tutoring, clean_text_qa,to_markdown
from rag.services.rag import retrieve_docs

# 從環境變數中取得 API key
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("未找到 GOOGLE_API_KEY，請確認已設定在 .env 檔中。")
# 初始化 Gemini
client = genai.Client(api_key=API_KEY)
model = "gemini-2.0-flash"

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






