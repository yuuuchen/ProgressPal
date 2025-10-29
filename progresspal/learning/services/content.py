# -*- coding: utf-8 -*-
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter 
from langchain_community.vectorstores import Chroma 
from langchain_community.embeddings import HuggingFaceEmbeddings 
from langchain.schema import Document
import re
import numpy as np
import os
from django.conf import settings

"""
建立教材向量庫
"""
#定義共用路徑
PERSIST_DIR = os.path.join(settings.TEACHING_MATERIAL_DIR, 'material_db')
db_path = os.path.join(PERSIST_DIR, "chroma.sqlite3")

#讀取資料夾裡的所有.md檔案
md_files = [f for f in os.listdir(settings.TEACHING_MATERIAL_DIR) if f.endswith(".md")]
all_docs = []

#定義標題層級
headers_to_split_on = [
    ("#", "章節"),
    ("##", "單元"),
    ("###", "段落"),
    ("####", "子段落")
]
markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

for file in md_files:
  file_path = os.path.join(settings.TEACHING_MATERIAL_DIR, file)

  #讀取檔案
  loader = TextLoader(file_path, encoding="utf-8")
  docs = loader.load()

  for d in docs:
    #MarkdownHeaderTextSplitter分段
    md_header_splits = markdown_splitter.split_text(d.page_content)

    for doc in md_header_splits:
      header = doc.metadata.get("段落", "")
      content_with_header = f"{header}\n{doc.page_content}" if header else doc.page_content

      all_docs.append(
        Document(
          page_content=content_with_header,
          metadata={
              **doc.metadata,   # 保留章節、小節資訊
              "source": file    # 加上檔名來源
          }
        )
      )

#檢查資料庫是否已存在
if not os.path.exists(db_path):
    if not all_docs:
        print("找不到任何 .md 檔案可供建立資料庫。")
    else:
        #將文本轉為向量
        print("正在載入 embeddings 模型...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        #存入 Chroma 向量資料庫
        print("正在建立 Chroma 向量資料庫並儲存...")
        vectorstore = Chroma.from_documents(
            documents=all_docs,
            embedding=embeddings,
            persist_directory=PERSIST_DIR,
        )
        vectorstore.persist()
        print(f"資料庫已成功建立")
else:
  print("已建立向量資料庫，略過重建")

"""**回傳教材內容**"""

#排序單元編號
def parse_unit_code(unit_code):
  parts = unit_code.split("-")
  nums = []
  for p in parts[:2]:  # 只取前兩項：章節與單元
    match = re.match(r"(\d+)", p)
    if match:
      nums.append(int(match.group(1)))
    else:
      nums.append(0)
  return nums  #回傳一個數字列表，例如 "1-1-1" → [1,1]

#依據章節與單元號碼，輸出該單元的教材內容字串
def get_unit(chapter, unit):
  docs_dict = {}

  for doc in all_docs:
    text = doc.page_content.strip()
    meta = doc.metadata

    unit_title = meta.get("單元", "")
    paragraph = meta.get("段落", "")
    if unit_title:
      unit_num = re.match(r"(\d+-\d+)", unit_title).group(0)  # 抓單元開頭數字

      if unit_num not in docs_dict:
        docs_dict[unit_num] = []

      # 在內容中保留段落資訊
      docs_dict[unit_num].append(f"{text}")

  target_code = f"{chapter}-{unit}" #組合成目標單元編號

  combined = []
  for key in sorted(docs_dict.keys(), key=parse_unit_code):
    if key == target_code:
      combined.append(f"=== {key} ===")
      combined.extend(docs_dict[key])

  if combined:
    return "\n".join(combined)
  else:
    return None

#依據章節，輸出該單元的教材內容字串
def get_chapter(chapter):
  docs_dict = {}

  for doc in all_docs:
    text = doc.page_content.strip()
    meta = doc.metadata

    unit_title = meta.get("單元", "")
    if unit_title:
      unit_num = re.match(r"(\d+-\d+)", unit_title).group(0)  # 抓單元編號

      if unit_num not in docs_dict:
        docs_dict[unit_num] = []

      # 在內容中保留原文
      docs_dict[unit_num].append(text)

  # 找出所有屬於該章節的單元
  combined = []
  for key in sorted(docs_dict.keys(), key=parse_unit_code):
    if key.startswith(f"{chapter}-"):  # 判斷章節開頭
      combined.append(f"=== {key} ===")
      combined.extend(docs_dict[key])

  if combined:
    return "\n".join(combined)
  else:
    return None

