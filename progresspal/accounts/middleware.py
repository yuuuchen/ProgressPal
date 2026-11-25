from learning.services.llm_model import llm_usage, user_api_key

from .api_key_session import load_api_key


class UserGroqKeyMiddleware:
    """
    在每個請求期間：
    - 把 Session 中受試者自己的 Groq API Key 放進 context，
      讓 learning.services.llm_model.get_rotational_client() 優先使用它；
    - 建立這個請求的 LLM 使用紀錄（是否用到伺服器備援 key）。
    需放在 SessionMiddleware 與 AuthenticationMiddleware 之後。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        key = load_api_key(request) if user is not None and user.is_authenticated else ""
        key_token = user_api_key.set(key)
        usage_token = llm_usage.set({"fallback": False})
        try:
            return self.get_response(request)
        finally:
            llm_usage.reset(usage_token)
            user_api_key.reset(key_token)
