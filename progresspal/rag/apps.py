import os
import sys
import threading

from django.apps import AppConfig


def _should_preload():
    """
    只在真正提供網頁服務的程序預載 RAG 模型：
    - runserver：autoreloader 會開兩個程序，只有子程序（RUN_MAIN=true）處理請求；加 --noreload 時則只有一個程序
    - migrate、shell、test 等其他 manage.py 指令不預載，避免每次都多花時間載入模型
    - 不是透過 manage.py 啟動（例如 gunicorn / WSGI）時預載
    設定環境變數 RAG_PRELOAD=0 可關閉預載。
    """
    if os.environ.get("RAG_PRELOAD", "1") == "0":
        return False
    argv = sys.argv
    if "runserver" in argv:
        return os.environ.get("RUN_MAIN") == "true" or "--noreload" in argv
    return not os.path.basename(argv[0] if argv else "").startswith("manage.py")


def _warm_up_rag():
    try:
        from rag.services.rag import warm_up
        warm_up()
    except Exception as e:
        # 預載失敗不影響網站運作，第一次提問時會照原本的方式再載入
        print(f"RAG 預載失敗，將在第一次提問時載入: {e}")


class RagConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rag'

    def ready(self):
        if _should_preload():
            # 背景執行：server 不用等模型載完才啟動，載完前進來的提問會等預載完成
            threading.Thread(target=_warm_up_rag, name="rag-warm-up", daemon=True).start()
