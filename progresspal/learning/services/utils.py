# -*- coding: utf-8 -*-
# utils.py
import textwrap
import re
from collections import Counter

"""格式整理工具"""

def clean_text_tutoring(raw_text: str) -> dict:
    """
    將 Markdown 格式 (觀念導讀、核心解析、範例、引導提問、提示) 轉成 dict
    """

    sections = {
        "guide": "",
        "core": "",
        "example": "",
        "extended_question": "",
        "hint": ""
    }

    raw_text = raw_text.strip() + "\n"

    # 這樣 #### 核心觀點 或是其他次級標題就會被當作內文完整保留。
    pattern = r"###\s*(觀念導讀|核心解析|範例|引導提問|提示)\s*[:：]?\s*([\s\S]*?)(?=\n###\s*(?:觀念導讀|核心解析|範例|引導提問|提示)|\Z)"
    matches = re.findall(pattern, raw_text)

    for title, content in matches:
        content = content.strip()

        if title == "觀念導讀":
            sections["guide"] = content
        
        elif title == "核心解析":
            sections["core"] = content

        elif title == "範例":
            sections["example"] = content

        elif title == "引導提問":
            sections["extended_question"] = content

        elif title == "提示":
            sections["hint"]= content

    # fallback
    if not sections["guide"]:
        sections["guide"] = "（模型未輸出觀念導讀）"

    if not sections["core"]:
        sections["core"] = "（模型未輸出核心解析）"

    if not sections["extended_question"]:
        sections["extended_question"] = "模型未輸出問題" 
    # print(f"[Debug] clean_text_tutoring 解析結果: {sections}")
    return sections

def clean_text_qa(raw_text: str) -> dict:
  """
  將 QA 模式回應解析成 dict
  {
      "answer": "回答內容",
      "extended_question": "引導提問",
      "hint": "提示"
  }
  """
  sections = {"answer": "", "extended_question": "", "hint": ""}

  # 確保最後有換行，避免最後一段抓不到
  raw_text = raw_text.strip() + "\n"

  # 匹配兩個區塊
  pattern = r"###\s*(回答問題|引導提問|提示)\s*([\s\S]*?)(?=\n###|\Z)"
  matches = re.findall(pattern, raw_text)

  for title, content in matches:
    content = content.strip()
    if title == "回答問題":
        sections["answer"] = content
    elif title == "引導提問":
        sections["extended_question"] = content
    elif title == "提示":
        sections["hint"]= content

  if not sections["answer"]:
      sections["answer"] = "（模型未輸出回答）"
  if not sections["extended_question"]:
      sections["extended_question"] = "（模型未輸出回答）"

  return sections

def to_markdown(text):
  if not text:
        return ""
  # 統一將特殊的中圓點替換為標準 Markdown 符號，方便前端解析
  text = text.replace('•', '*') 
  return text.strip()


# 測驗關鍵字抓取工具
class KeywordAnalyzer:
    KEYWORD_MAP = {
        # ================= CH1 陣列 =================
        "CH1_結構": ["陣列", "array", "list", "索引", "index", "連續"],
        "CH1_操作": ["插入", "刪除", "遍歷", "搜尋", "存取"],
        "CH1_時間複雜度": ["時間複雜度", "O(", "效率"],

        # ================= CH2 鏈結串列 =================
        "CH2_結構": ["節點", "node", "next", "prev", "頭節點", "尾節點", "環狀"],
        "CH2_操作": ["插入", "刪除", "順序", "操作", "程式碼"],
        "CH2_時間複雜度": ["時間複雜度", "O(", "效率"],
        "CH2_應用": ["LRU", "排程", "佇列", "圖"],

        # ================= CH3 堆疊 =================
        "CH3_結構": ["堆疊", "stack", "LIFO", "後進先出"],
        "CH3_操作": ["push", "pop", "peek", "操作"],
        "CH3_應用": ["括號", "表達式", "undo", "呼叫堆疊"],

        # ================= CH4 佇列 =================
        "CH4_結構": ["佇列", "queue", "FIFO", "先進先出"],
        "CH4_操作": ["enqueue", "dequeue", "操作"],
        "CH4_應用": ["bfs", "排程", "訊息", "buffer"],
    }

    @classmethod
    def extract_keywords(cls, question_text):
        text = question_text.lower()
        found = []

        for label, keywords in cls.KEYWORD_MAP.items():
            for kw in keywords:
                if kw.lower() in text:
                    found.append(label)
                    break

        return found
    
    @classmethod
    def count_keywords(cls, question_list, chapter_filter=None, top_n=5):
        """
        統計 question_list 中出現的 keyword 次數
        chapter_filter: 指定 CH1~CH4 篩選
        top_n: 取前 N 名
        """
        counter = Counter()

        for q in question_list:
            q_text = q.question.question if hasattr(q, 'question') else q
            keywords = cls.extract_keywords(q_text)

            for kw in keywords:
                if chapter_filter:
                    if f"CH{chapter_filter}_" in kw:
                        counter[kw] += 1
                else:
                    counter[kw] += 1

        return counter.most_common(top_n)