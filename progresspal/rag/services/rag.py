# -*- coding: utf-8 -*-
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
import re
from rank_bm25 import BM25Okapi
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import os
import jieba
from learning.services.content import all_docs
from django.conf import settings

PERSIST_DIR = os.path.join(settings.TEACHING_MATERIAL_DIR, 'material_db')

try:
  embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
  vectorstore = Chroma(
      persist_directory=PERSIST_DIR, 
      embedding_function=embeddings
  )
except Exception as e:
  print(f"載入向量資料庫失敗。")
  vectorstore = None 

"""**Chroma + BM25 混合搜尋**"""

def retrieve_docs(query, top_k=5, weight_bm25=0.7, weight_vector=0.3):
  if not vectorstore:
    print("向量資料庫未載入")
    return [] # 回傳空列表
  
  #取得關鍵字
  keywords = query.get("keywords", [])
  results = []  # 最終結果

  #遍歷每個關鍵字
  for keyword in keywords:
    #先在metadata章節中過濾出包含該關鍵字的段落
    #沒有符合就改用全教材搜尋
    filtered_docs = [doc for doc in all_docs if keyword in doc.metadata.get("章節", "")]
    corpus_docs = filtered_docs if filtered_docs else all_docs
    corpus_texts = [doc.page_content for doc in corpus_docs]

    #BM25準備，jieba做全模式分詞
    tokenized_corpus = [list(jieba.cut(text, cut_all=True)) for text in corpus_texts]
    #建立BM25模型
    bm25 = BM25Okapi(tokenized_corpus)
    query_tokens = list(jieba.cut(keyword, cut_all=True))
    bm25_scores = bm25.get_scores(query_tokens)

    #排序候選文件
    bm25_ranked = sorted(
        zip(bm25_scores, corpus_texts),
        key=lambda x: x[0],
        reverse=True
    )

    #metadata篩選
    if filtered_docs:
      candidate_pairs = bm25_ranked[:10]  #章節內取前10
    #全教材搜尋
    else:
      candidate_pairs = [(score, doc) for score, doc in bm25_ranked if score > 0][:10] #過濾出score>0，再取前10

    #如果沒有任何候選，就跳到下一個keyword
    if not candidate_pairs:
      continue

    candidate_docs = [doc for _, doc in candidate_pairs]
    bm25_scores_candidates = np.array([score for score, _ in candidate_pairs])

    #向量檢索
    query_emb = embeddings.embed_query(keyword)
    vector_scores = []
    for doc in candidate_docs:
        doc_emb = embeddings.embed_documents([doc])[0]
        score = np.dot(query_emb, doc_emb) / (
            np.linalg.norm(query_emb) * np.linalg.norm(doc_emb)
        )
        vector_scores.append(score)
    vector_scores = np.array(vector_scores)

    #標準化分數
    def normalize(arr):
      if len(arr) > 1:
        return (arr - np.min(arr)) / (np.ptp(arr) + 1e-9)
      else:
        return np.array([1.0])  # 單一元素直接給 1

    bm25_scores_norm = normalize(bm25_scores_candidates)
    vector_scores_norm = normalize(vector_scores)

    #融合分數
    final_scores = weight_bm25 * bm25_scores_norm + weight_vector * vector_scores_norm

    #排序/取前 top_k
    sorted_pairs = sorted(
        zip(final_scores, candidate_docs),
        key=lambda x: x[0],
        reverse=True
    )
    top_docs = [doc for _, doc in sorted_pairs[:top_k]]

    #去除重複段落
    for doc in top_docs:
      if doc not in results:
        results.append(doc)

  return results if results else None  #回傳結果list，[]為空則回傳None
