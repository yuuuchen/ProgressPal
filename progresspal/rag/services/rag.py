# -*- coding: utf-8 -*-
import os
import jieba
import numpy as np
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from rank_bm25 import BM25Okapi
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

    print("載入 Multilingual-E5 Embeddings")
    _embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-base",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

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

def _normalize_content_key(content):
    """
    剝離 Chroma 內部的 'passage: ' 前綴，確保與本地 all_docs 的文本能精確進行 RRF 字典聯集。
    """
    if content.startswith("passage: "):
        return content[9:].strip()
    return content.strip()

def hybrid_search(query_for_vector, query_for_bm25, original_question=None, k=3, weight_bm25=0.3, weight_vector=0.7):
    """
    Step 1: 雙路放寬抓取 candidate_k=10 (高召回率廣積糧)
    Step 2: 透過 RRF 數學公式融合兩路排名 (免疫 BM25 離群值與尺度干擾)
    """
    vectorstore = get_vectorstore()
    bm25_model = get_bm25()

    if not vectorstore:
        print("向量資料庫未載入")
        return []

    candidate_k = 10
    
    # 1. 密集向量檢索 (傳入已帶有 "query: " 的語句)
    vec_results = vectorstore.similarity_search_with_score(query_for_vector, k=candidate_k)

    # 2. 稀疏關鍵字檢索 (BM25)
    query_tokens = list(jieba.cut(query_for_bm25, cut_all=False))
    stop_words = {'的', '是', '什麼', '甚麼', '嗎', '與', '和', '?', '定義', ' ', '\n', '有哪些','。'}
    filtered_tokens = [t for t in query_tokens if t not in stop_words] or query_tokens

    if bm25_model:
        bm25_scores_all = bm25_model.get_scores(filtered_tokens)
        top_bm25_indices = np.argsort(bm25_scores_all)[::-1][:candidate_k]
    else:
        bm25_scores_all = []
        top_bm25_indices = []

    # 建立全局 Document 映射表與名次追蹤器
    doc_map = {}

    # 記錄向量軌道的排名位置
    vec_ranks = {}
    for rank_idx, (doc, _) in enumerate(vec_results):
        # 將從 Chroma 撈出來的 content 進行前綴剝離，歸一化後再當做 Dict Key
        norm_key = _normalize_content_key(doc.page_content)
        doc.page_content = norm_key  # 順手將物件內的文本洗乾淨，防範任何字串洩漏到前端
        doc_map[norm_key] = doc
        vec_ranks[norm_key] = rank_idx + 1  # 1-indexed 名次

    # 記錄 BM25 軌道的排名位置
    bm25_ranks = {}
    for rank_idx, idx in enumerate(top_bm25_indices):
        if bm25_scores_all[idx] <= 0:
            continue
        content = all_docs[idx].page_content
        norm_key = _normalize_content_key(content)
        
        # 確保映射表裡儲存的是已被清洗乾淨的 Document
        all_docs[idx].page_content = norm_key
        doc_map[norm_key] = all_docs[idx]
        bm25_ranks[norm_key] = rank_idx + 1

    # 執行 RRF (倒數排名融合) 演算法
    rrf_results = []
    all_candidates = set(vec_ranks.keys()).union(set(bm25_ranks.keys()))

    for content in all_candidates:
        r_vec = vec_ranks.get(content, 999)    # 若向量沒撈到，降級給予極低名次
        r_bm25 = bm25_ranks.get(content, 999)  # 若 BM25 沒撈到，降級給予極低名次

        # 改用 RRF 排名倒數融合公式，乘以指定的權重參數
        rrf_score = (weight_vector / (60 + r_vec)) + (weight_bm25 / (60 + r_bm25))
        
        # 紀錄最終融合分數至 metadata 方便除錯與追蹤
        doc_map[content].metadata["score"] = float(rrf_score)
        rrf_results.append((doc_map[content], rrf_score))

    # 依照 RRF 融合分數由高到低大排行
    rrf_results.sort(key=lambda x: x[1], reverse=True)

    # 回傳大排行表現最優的前 k 個純淨 Document 物件
    results = [doc for doc, score in rrf_results[:k]]
    return results if results else None

def retrieve_docs(query, top_k=3, weight_bm25=0.3, weight_vector=0.7):
    query_for_vector = f"query: {query}"
    query_for_bm25 = query
    
    return hybrid_search(
        query_for_vector=query_for_vector,
        query_for_bm25=query_for_bm25,
        original_question=query,
        k=top_k,
        weight_bm25=weight_bm25,
        weight_vector=weight_vector
    )

def clean_doc_content(item):
    doc = item[0] if isinstance(item, tuple) else item
    content = doc.page_content
    return _normalize_content_key(content)