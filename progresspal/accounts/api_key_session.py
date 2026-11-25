"""
受試者的 Groq API Key 只存在 Django Session（以 accounts/crypto.py 加密），
不寫入使用者資料表。Session 於登出或 SESSION_COOKIE_AGE（8 小時）後失效；
實驗結束時執行 `python manage.py clearsessions` 即清除所有殘留的 key。
"""
from .crypto import decrypt, encrypt

SESSION_FIELD = "groq_api_key"


def store_api_key(request, api_key):
    request.session[SESSION_FIELD] = encrypt(api_key)


def load_api_key(request):
    session = getattr(request, "session", None)
    if session is None:
        return ""
    return decrypt(session.get(SESSION_FIELD, ""))
