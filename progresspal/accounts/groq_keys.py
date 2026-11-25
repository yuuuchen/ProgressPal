"""驗證使用者提供的 Groq API Key（只列出模型，不消耗 token）。"""
from groq import APIConnectionError, APIStatusError, AuthenticationError, Groq


def validate_groq_api_key(api_key):
    """有效時回傳 None，否則回傳給使用者看的錯誤訊息。"""
    try:
        Groq(api_key=api_key, timeout=10, max_retries=1).models.list()
    except AuthenticationError:
        return "這把 API Key 無效或已過期，請到 Groq 重新建立一把。"
    except APIConnectionError:
        return "目前無法連線到 Groq 驗證 API Key，請稍後再試。"
    except APIStatusError as e:
        if "organization_restricted" in str(e):
            return "這把 API Key 所屬的 Groq 帳號已被停權，請改用其他帳號建立的 Key。"
        return f"Groq 驗證 API Key 失敗（{e.status_code}），請稍後再試。"
    return None
