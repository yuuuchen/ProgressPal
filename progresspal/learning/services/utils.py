# -*- coding: utf-8 -*-
# utils.py
import textwrap
from markdown import markdown

"""格式整理工具"""

def clean_text_tutoring(raw_text: str) -> dict:
  import re
  """
  將 Markdown 格式 (含 ### 教學重點、範例、總結、引導提問) 轉成 dict
  """
  sections = {
      "teaching": "",
      "example": "",
      "summary": "",
      "extended_question": ""
  }

  # 確保最後有換行，避免最後一段抓不到
  raw_text = raw_text.strip() + "\n"

  # 改良正則，多行匹配
  pattern = r"###\s*(教學重點|範例|總結|引導提問)\s*([\s\S]*?)(?=\n###|\Z)"
  matches = re.findall(pattern, raw_text)

  for title, content in matches:
    content = content.strip()
    if title == "教學重點":
        sections["teaching"] = content
    elif title == "範例":
        sections["example"] = content
    elif title == "總結":
        sections["summary"] = content
    elif title == "引導提問":
        sections["extended_question"] = content

  if not sections["summary"]:
    sections["summary"] = "（模型未輸出）"
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
  html_output = markdown(text, extensions=['fenced_code', 'nl2br', 'tables'])
  return html_output

def split_extended_questions(text):
    """
    將 AI 回傳的一串延伸提問文字拆成陣列
    """
    if not text:
        return []

    lines = text.split("\n")

    questions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        cleaned = re.sub(r"^(\d+\.|\d+\)|[-•])\s*", "", line)
        if cleaned:
            questions.append(cleaned)

    return questions