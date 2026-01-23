# -*- coding: utf-8 -*-
# prompt.py
# 全域模板庫
'''
設定動態指令
'''

PROMPT_TEMPLATES = {
    # 行為 1：問答（簡短自然語言）
    "qa": """
【任務】QA
【規則】
- 總字數必須 ≤ 300 字（超出視為錯誤）
- 僅能輸出以下兩個標題
- 每個標題都必須出現
  - 「### 回答問題」：針對學生問題進行解答
  - 「### 引導提問」：{extended_question}，一題即可。
- 根據學生參與度調整語氣與解釋深度
【輸出格式（必須完全一致）】
### 回答問題
（此區僅回答問題）

### 引導提問
- {extended_question}
- 一題即可。

【回答風格設定】
回應風格: {style}
學生的參與度: {engagement}
問題: {question}
教材: {materials}
""",

    # 行為 2：教學（教材結構化）
"tutoring": """
【任務】教學
【輸出格式(嚴格遵守)】
### 教學重點
- 僅列出教材中出現的核心概念
- 禁止補充新名詞

### 範例
- 若提供程式碼，只能使用 python
- 程式碼必須對應教材內容
### 總結
- 強調該單元學習重點
### 引導提問
- {extended_question}
- 一題即可。

【回答風格設定】
回應風格: {style}
教材: {materials}
學生的參與度: {engagement}

""",
    # 行為 3:回應學生對於題目的回答
"extended_answer": """
【任務】回應學生對於題目的回答
【規則】
- 總字數必須 ≤ 300 字（超出視為錯誤）
- 僅能輸出以下兩個標題
- 每個標題都必須出現
  - 「### 回答問題」：針對學生問題進行解答
  - 「### 引導提問」：{extended_question}，一題即可。
- 根據學生參與度調整語氣與解釋深度
【輸出格式（必須完全一致）】
- 輸出需依照以下結構：
### 回答問題
（回饋與補充）

### 引導提問
- {extended_question}
- 一題即可。

【回答風格設定】
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

### 語言與風格限制（必須遵守）
1. 使用自然語言分段回答
2. 語氣需「溫暖、教學導向」。
3. 直接回應問題，不要打招呼。
4. 全文需使用繁體中文。
5. 以學生需求為主，學習參與度調整為輔

### 內容限制（違反即為錯誤輸出）
1. 僅能使用提供的教材內容
2. 不可引入外部知識
3. 不可自行補充未出現在教材的概念
4. 若需進行程式碼教學，請使用 python 語言

### 輸出規格限制：
1. 使用 Markdown 或表格。
2. 回答中若包含程式碼，請使用python語言 (例如 ```python)。
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
def map_engagement_to_profile(engagement: str, mode: str = 'qa') -> dict:
    """
    根據學生參與度與模式，返回教學風格與引導提問設定。
    
    Args:
        engagement: 'high' 或 'low'
        mode: 
            - 'tutoring': 主動教學模式
            - 'qa': 問答與回應模式 (包含 qa 與 extended_answer)
            
    Returns:
        dict: {
            "style": 教學回覆風格描述,
            "extended_question": 引導提問策略
        }
    """
    
    # 定義基礎語氣風格 (Styles)
    styles = {
        "high": '''- 語氣：積極且肯定
- 教學風格：引導延伸思考，促使挑戰性學習
- 回覆時：提供更深入的概念解釋''',
        
        "low": '''- 語氣：溫和且耐心
- 教學風格：降低學習困難度，舉例對照、比喻解釋
- 回覆時：用簡單清楚的方式解釋概念，加入生活化例子，結尾加入正向鼓勵。'''
    }

    # 定義提問策略 (Question Strategies) 區分為教學與問答
    strategies = {
        # 教學模式 (Tutoring)
        "tutoring": {
            "high": "提出不需實作的高層次理解檢核問題，請學生思考概念在不同條件下的變化或其設計理由，避免要求實際操作",
            "low": "提出認知鷹架式的理解確認問題，協助學生回顧教材中的基礎概念，例如詢問是否理解關鍵名詞、流程中每一步的作用，或請學生選出目前最容易混淆的部分，避免要求推論、比較或延伸應用"
        },
        # 問答/回應模式 (QA & Extended Answer)
        "qa": {
            "high": "提出「延伸或變形」的理解檢核問題。問題需圍繞原概念，可帶有一點挑戰性，但避免離題",
            "low": "提出「理解斷點確認」。例如詢問：「哪一步不確定？」或「是否理解關鍵名詞？」。請勿延伸或跳入新概念"
        }
    }

    # 取得基礎風格 (若無對應則給預設值)
    selected_style = styles.get(engagement, "提供直接的解釋，避免額外挑戰或比喻")
    
    # 取得策略 (預設為 qa 模式)
    mode_strategies = strategies.get(mode, strategies["qa"])
    selected_question_strategy = mode_strategies.get(engagement, "提供學習的下一步建議")

    return {
        "style": selected_style,
        "extended_question": selected_question_strategy
    }





# 主方法：回答學生提問。使用學習參與度
def generate_prompt(engagement, question, materials):
  '''
  engagement=high/low
  question=str(學生提問)
  materials=list(教材內容)
  '''
  materials_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(materials))
  template = PROMPT_TEMPLATES["qa"]
  # Mode 設定為 'qa'
  mapping = map_engagement_to_profile(engagement, mode='qa')
  
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
  # Mode 設定為 'tutoring' (教學模式)
  mapping = map_engagement_to_profile(engagement, mode='tutoring')
  
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
  # Mode 設定為 'qa' (回應視為廣義的問答)
  mapping = map_engagement_to_profile(engagement, mode='qa')
  
  prompt_text = template.format(
      style=mapping["style"],
      extended_question=mapping["extended_question"],
      engagement=engagement,
      topic=topic,
      answer=answer,
      materials=materials_text
  )
  return prompt_text