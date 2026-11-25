import contextvars

from dotenv import load_dotenv
from groq import Groq
from django.conf import settings

# 目前請求的使用者自己的 Groq API Key（來自 Session），由 accounts.middleware.UserGroqKeyMiddleware 設定
user_api_key = contextvars.ContextVar("user_api_key", default="")
# 目前請求的 LLM 使用狀況，例如 {"fallback": True} 表示有回應是用伺服器備援 key 產生的
llm_usage = contextvars.ContextVar("llm_usage", default=None)


def fallback_key_used():
    """目前這個請求中，是否有任何 LLM 回應改用了伺服器的備援 key"""
    usage = llm_usage.get()
    return bool(usage and usage.get("fallback"))


class RotationalGroqClient:
    """自動輪替 Groq API Keys 的 Client"""
    def __init__(self, api_keys=None, server_key_start=0):
        # 預先處理好 keys，避免每次呼叫都做字串處理
        raw_keys = api_keys if api_keys is not None else getattr(settings, "GROQ_API_KEYS", [])
        self.api_keys = [str(k).strip().replace('"', '').replace("'", "") for k in raw_keys if k]
        # api_keys 中從這個位置開始是伺服器的 key（前面是使用者自己的）
        self.server_key_start = server_key_start

    def _record_key_use(self, index):
        if index >= self.server_key_start:
            usage = llm_usage.get()
            if usage is not None:
                usage["fallback"] = True

    def _get_client(self, index):
        """內部私有方法：建立 Client"""
        return Groq(api_key=self.api_keys[index])

    def _should_rotate(self, error_msg):
        """判斷是否應該切換下一個 Key"""
        error_msg = error_msg.lower()
        # 增加 413, 503, 500 等常見錯誤的自動輪替
        # 401 / 403 / organization_restricted：這把 key 失效或帳號被停權，換下一把
        retry_codes = ["429", "rate_limit", "401", "403", "organization_restricted", "413", "503", "500", "overloaded"]
        return any(code in error_msg for code in retry_codes)

    # def generate_qa_content(self, model, messages, temperature=0.3, max_tokens=1024):
    #     """Llama 模型專用：標準問答"""
    #     last_error = None           
    #     for index in range(len(self.api_keys)):
    #         try:
    #             client = self._get_client(index)
    #             response = client.chat.completions.create(
    #                 model=model,
    #                 messages=messages,
    #                 temperature=temperature,
    #                 max_completion_tokens=max_tokens # 建議統一使用 max_completion_tokens
    #             )                   
    #             return response.choices[0].message.content
    #         except Exception as e:
    #             error_msg = str(e)
    #             print(f"[除錯] QA Key #{index+1} 錯誤: {error_msg}")
    #             if self._should_rotate(error_msg):
    #                 last_error = e
    #                 continue 
    #             raise e           
    #     raise RuntimeError("所有 QA API Key 的流量都已耗盡或觸發限制。") from last_error

    def generate_content(self, model, messages, temperature=0, max_tokens=2048):
        """gpt-oss-120b 專用：低推理教材生成"""
        last_error = None           
        for index in range(len(self.api_keys)):
            try:
                client = self._get_client(index)
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_tokens, 
                    top_p=1,
                    stream=False
                )
                self._record_key_use(index)
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                print(f"[除錯] Materials Key #{index+1} 錯誤: {error_msg}")
                if self._should_rotate(error_msg):
                    last_error = e
                    continue 
                raise e           
        raise RuntimeError("所有 Materials API Key 的流量都已耗盡或觸發限制。") from last_error
    
def get_rotational_client():
    """
    使用者有自己的 key 時優先使用；伺服器 .env 的 key 作為備援。
    設定 GROQ_FALLBACK_TO_SERVER_KEYS = False 可關閉備援，只用使用者自己的 key。
    """
    own_key = user_api_key.get()
    keys = [own_key] if own_key else []
    if not own_key or getattr(settings, "GROQ_FALLBACK_TO_SERVER_KEYS", True):
        keys += [k for k in getattr(settings, "GROQ_API_KEYS", []) if k and k != own_key]
    return RotationalGroqClient(keys, server_key_start=1 if own_key else 0)

model = "openai/gpt-oss-120b"

# model_qa = "llama-3.3-70b-versatile"
# model_materials = "openai/gpt-oss-120b"