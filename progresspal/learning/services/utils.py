# -*- coding: utf-8 -*-
# utils.py
import textwrap
import re
from markdown import markdown

"""格式整理工具"""

def clean_text_tutoring(raw_text: str) -> dict:
    import re
    """
    將 Markdown 格式 (觀念導讀、核心解析、範例、引導提問) 轉成 dict
    並將「觀念導讀 + 核心解析」合併為 teaching
    """

    sections = {
        "teaching": "",
        "example": "",
        "extended_question": ""
    }

    raw_text = raw_text.strip() + "\n"

    pattern = r"###\s*(觀念導讀|核心解析|範例|引導提問)\s*[:：]?\s*([\s\S]*?)(?=\n###|\Z)"
    matches = re.findall(pattern, raw_text)

    teaching_parts = []

    for title, content in matches:
        content = content.strip()

        if title in ["觀念導讀", "核心解析"]:
            teaching_parts.append(content)

        elif title == "範例":
            sections["example"] = content

        elif title == "引導提問":
            sections["extended_question"] = content

    # 合併教學內容
    sections["teaching"] = "\n\n".join(teaching_parts)

    # fallback
    if not sections["teaching"]:
        sections["teaching"] = "（模型未輸出教學內容）"

    if not sections["extended_question"]:
        sections["extended_question"] = "模型未輸出問題"

    return sections

def clean_text_qa(raw_text: str) -> dict:
  import re
  """
  將 QA 模式回應解析成 dict
  {
      "answer": "回答內容",
      "extended_question": "引導提問"
  }
  """
  sections = {"answer": "", "extended_question": ""}

  # 確保最後有換行，避免最後一段抓不到
  raw_text = raw_text.strip() + "\n"

  # 匹配兩個區塊
  pattern = r"###\s*(回答問題|引導提問)\s*([\s\S]*?)(?=\n###|\Z)"
  matches = re.findall(pattern, raw_text)

  for title, content in matches:
      content = content.strip()
      if title == "回答問題":
          sections["answer"] = content
      elif title == "引導提問":
          sections["extended_question"] = content

  if not sections["answer"]:
      sections["answer"] = "（模型未輸出回答）"
  if not sections["extended_question"]:
      sections["extended_question"] = "（模型未輸出回答）"

  return sections

def to_markdown(text):
  text = text.replace('•', '  *')
  html_output = markdown(text, extensions=['fenced_code', 'nl2br', 'tables','mdx_math'])
  return html_output