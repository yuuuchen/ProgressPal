# -*- coding: utf-8 -*-
import os
import jieba
import numpy as np
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from rank_bm25 import BM25Okapi
from sklearn.preprocessing import MinMaxScaler
from django.conf import settings
from learning.services.content import all_docs


PERSIST_DIR = os.path.join(settings.TEACHING_MATERIAL_DIR, 'material_db')
db_path = os.path.join(PERSIST_DIR, "chroma.sqlite3")

_vectorstore = None 
_embeddings = None 
_bm25 = None
_bm25_corpus_indices = None

"""
延遲載入，避免 reload 時重建 DB
"""
def get_vectorstore():
    global _vectorstore, _embeddings

    if _vectorstore is not None:
        return _vectorstore

    if not os.path.exists(db_path):
        print("請先執行建立資料庫。")
        return None

    print("載入 HuggingFaceEmbeddings")
    _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print("載入現有 Chroma 資料庫")
    _vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=_embeddings
    )
    return _vectorstore

"""**Chroma + BM25 混合搜尋**"""
def get_bm25():
    """
    取得 BM25 物件。
    只在第一次呼叫時建立索引，大幅提升後續搜尋速度。
    """
    global _bm25, _bm25_corpus_indices
    
    if _bm25 is not None:
        return _bm25

    print("正在建立 BM25 索引")
    if not all_docs:
        print("警告：all_docs 為空，無法建立 BM25")
        return None

    # 對所有教材進行分詞
    tokenized_corpus = []
    # 使用 all_docs 的索引來做對應
    _bm25_corpus_indices = list(range(len(all_docs)))
    
    for doc in all_docs:
        # 使用精確模式分詞，並去除換行符
        tokens = list(jieba.cut(doc.page_content.replace('\n', ''), cut_all=False))
        tokenized_corpus.append(tokens)

    _bm25 = BM25Okapi(tokenized_corpus)
    print("BM25 索引建立完成。")
    return _bm25

def retrieve_docs(query, top_k=3, weight_bm25=0.7, weight_vector=0.3):
    vectorstore = get_vectorstore()
    bm25_model = get_bm25()

    if not vectorstore:
        print("向量資料庫未載入")
        return [] # 回傳空列表
  
    # 設定候選數量
    candidate_k = 10

    # 向量搜尋 (Vector Search)
    vec_results = vectorstore.similarity_search_with_score(query, k=candidate_k)
    
    # 關鍵字搜尋 (BM25)
    # 前處理 Query
    query_tokens = list(jieba.cut(query, cut_all=False))
    stop_words = {'的', '是', '什麼', '甚麼', '嗎', '與', '和', '?', '定義', ' ', '。', '，'}
    filtered_tokens = [t for t in query_tokens if t not in stop_words]
    if not filtered_tokens: 
        filtered_tokens = query_tokens
    
    # 計算 BM25 分數
    if bm25_model:
        bm25_scores = bm25_model.get_scores(filtered_tokens)
        # 取得分數最高的 indices
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:candidate_k]
    else:
        top_bm25_indices = []
        bm25_scores = []
    
    # 融合與標準化
    candidates = {}
    # 處理向量結果
    for doc, distance in vec_results:
        # 將距離轉為相似度分數
        sim_score = 1 / (1 + distance) 
        
        candidates[doc.page_content] = {
            "doc": doc,
            "vec_score": sim_score,
            "bm25_score": 0.0 # 先給預設值
        }

    # 處理 BM25 結果
    for idx in top_bm25_indices:
        score = bm25_scores[idx]
        if score <= 0: continue
        
        doc = all_docs[idx] # 從全域 docs 找回 document 物件
        
        if doc.page_content in candidates:
            # 如果已經在向量搜尋結果中，補上 BM25 分數
            candidates[doc.page_content]["bm25_score"] = score
        else:
            # 如果是 BM25 獨有的結果，加入候選
            candidates[doc.page_content] = {
                "doc": doc,
                "vec_score": 0.0, # 向量分數預設為 0
                "bm25_score": score
            }

    # 轉為列表準備標準化
    candidate_list = list(candidates.values())
    if not candidate_list:
        return []
    
    # 提取分數陣列
    vec_vals = np.array([x["vec_score"] for x in candidate_list])
    bm25_vals = np.array([x["bm25_score"] for x in candidate_list])

    # 標準化
    scaler = MinMaxScaler()

    # 標準化 Vector 分數
    if len(vec_vals) > 1 and np.std(vec_vals) > 1e-9:
        vec_norm = scaler.fit_transform(vec_vals.reshape(-1, 1)).flatten()
    else:
        vec_norm = vec_vals 

    # 標準化 BM25 分數
    if len(bm25_vals) > 1 and np.std(bm25_vals) > 1e-9:
        bm25_norm = scaler.fit_transform(bm25_vals.reshape(-1, 1)).flatten()
    else:
        bm25_norm = bm25_vals
    
    # 計算加權總分
    final_results = []
    for i, item in enumerate(candidate_list):
        final_score = (weight_vector * vec_norm[i]) + (weight_bm25 * bm25_norm[i])
        item["doc"].metadata["score"] = final_score # 將分數寫入 metadata 方便除錯
        final_results.append((item["doc"], final_score))

    # 排序 (分數高到低)
    final_results.sort(key=lambda x: x[1], reverse=True)

    # 取出 Document 物件
    results = [doc for doc, score in final_results[:top_k]]

    return results if results else None #回傳結果list，[]為空則回傳None
