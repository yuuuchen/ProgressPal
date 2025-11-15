# -*- coding: utf-8 -*-
# prompt.py
# 全域模板庫
'''
設定動態指令
'''

PROMPT_TEMPLATES = {
    # 行為 1：問答（簡短自然語言）
    "qa": """
任務：QA
- **回答問題**字數總計不得超過 200 字
- 根據學生參與度調整語氣與解釋深度
- 若提供程式碼請使用python語言
- 輸出需依照以下結構：
  - 「### 回答問題」：針對學生問題進行解答
  - 「### 引導提問」：{extended_question}共三項。

### 回答風格設定
回應風格: {style}
學生的參與度: {engagement}
問題: {question}
教材: {materials}
""",

    # 行為 2：教學（教材結構化）
"tutoring": """
任務：教學
輸出需依照以下結構：
  - 「### 教學重點」：解釋核心概念，理性陳述單元內容與重點。
  - 「### 範例」：提供簡單範例或 **python** 程式碼示例，並使用指定教學策略。
  - 「### 總結」：總結重點回顧，簡潔明瞭。
  - 「### 引導提問」：{extended_question}。共三項。

### 回答風格設定
回應風格: {style}
學生的參與度: {engagement}
教材: {materials}
""",
    # 行為 3:回應學生對於題目的回答
"extended_answer": """
任務：回應學生對於題目的回答
- **回答字數**總計不得超過 200 字
- 根據學生參與度調整語氣與解釋深度
- 若提供程式碼請使用python語言
- 輸出需依照以下結構：
  - 「### 回答問題」：針對學生的回答進行回饋與補充說明
  - 「### 引導提問」：根據教材，提出 3 個與該題相關的延伸思考問題，逐條列出

### 回答風格設定
回應風格: {style}
學生的參與度: {engagement}
題目: {topic}
學生回答: {answer}
教材: {materials}
"""

}
### 系統指令 System Prompt 包含變數identity

SYSTEM_PROMPT = """
你是一位智慧助教，專精於資料結構教學。
教學對象：{identity},{strategy}
你需要根據學生的「學習參與度」調整語氣、解釋深度與互動方式。

### 規則
1. 使用自然語言分段回答，可使用 Markdown 或表格。
2. 語氣需「溫暖、易於理解」。
3. 直接回應問題，不要打招呼。
4. 全文需使用繁體中文。
5. 請依照教材內容進行回應，請勿回應教材外的答案。
6. 範例使用語言標籤 (例如 ```python)
7. 以學生需求為主，學習參與度調整為輔
"""
def set_system_prompt(identity='資訊領域大學生'):
  '''
  input: identity
  return: new Systemprompt
  '''
  mapping = {
  '資訊領域大學生':'''請以專業術語講解，提供程式碼範例。''',
  '非資訊領域大學生':'''請循序漸進，不要一次丟太多資訊。避免使用專業術語。''',
  'mis_student':'''請以專業術語講解，提供程式碼範例。''',
  'normal_student':'''請循序漸進，不要一次丟太多資訊。避免使用專業術語。''',
  }
  strategy = mapping.get(identity, "請根據學生程度調整教學方式。")
  return SYSTEM_PROMPT.format(identity=identity, strategy=strategy)

#print(set_system_prompt("非資訊領域大學生"))


# 映射方法：參與度 → 語氣 + 教學策略
def map_engagement_to_profile(engagement: str) -> dict:
    """
    根據學生參與度返回教學風格與引導提問設定。
    engagement: 'high' 或 'low'
    回傳 dict 內含:
      - style: 教學回覆風格描述
      - extended_question: 引導提問策略
    """
    mapping = {
      "high": {
        "style": '''- 語氣：積極且肯定
- 教學風格：引導延伸思考，促使挑戰性學習
- 回覆時：提供更深入的概念解釋''',
        "extended_question": '根據教材，提出與學生問題相關的延伸思考問題或學習的下一步建議'
      },
      "low": {
        "style": '''- 語氣：溫和且耐心
- 教學風格：降低學習困難度，舉例對照、比喻解釋
- 回覆時：用簡單清楚的方式解釋概念，加入生活化例子，結尾加入正向鼓勵。''',
        "extended_question": '提出學生可能產生問題的原因，避免挑戰性問題或額外延伸'
      }
    }

    # 若傳入的 engagement 不在 mapping，提供預設安全回覆
    return mapping.get(engagement, {
        "style": "提供直接的解釋，避免額外挑戰或比喻",
        "extended_question": "提供學習的下一步建議"
    })




# 主方法：回答學生提問。使用學習參與度
def generate_prompt(engagement, question, materials):
  '''
  engagement=high/low
  question=str(學生提問)
  materials=list(教材內容)
  '''
  materials_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(materials))
  template = PROMPT_TEMPLATES["qa"]
  mapping=map_engagement_to_profile(engagement)
  prompt_text = template.format(
      style=mapping["style"],
      extended_question=mapping["extended_question"],
      engagement=engagement,
      question=question,
      materials=materials_text
  )
  return prompt_text


# 根據教材進行教學
def generate_materials(engagement ,materials):
  '''
  engagement=high/low
  materials=list(教材內容)
  '''
  materials_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(materials))
  template = PROMPT_TEMPLATES["tutoring"]
  mapping=map_engagement_to_profile(engagement)
  prompt_text = template.format(
      style=mapping["style"],
      engagement=engagement,
      materials=materials_text,
      extended_question=mapping["extended_question"]
  )
  return prompt_text

# 進行題目回應。使用學習參與度
def generate_prompt_extended(engagement, answer, materials,topic):
  '''
  engagement=high/low
  answer=str(學生回應)
  materials=list(教材內容)
  topic=str(題目)
  '''
  materials_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(materials))
  template = PROMPT_TEMPLATES["extended_answer"]
  mapping=map_engagement_to_profile(engagement)
  prompt_text = template.format(
      style=mapping["style"],
      extended_question=mapping["extended_question"],
      engagement=engagement,
      topic=topic,
      answer=answer,
      materials=materials_text
  )
  return prompt_text