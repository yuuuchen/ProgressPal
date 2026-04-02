from dotenv import load_dotenv
from groq import Groq
from django.conf import settings

class RotationalGroqClient:
    """自動輪替 Groq API Keys 的 Client"""
    def __init__(self):
        # 預先處理好 keys，避免每次呼叫都做字串處理
        raw_keys = getattr(settings, "GROQ_API_KEYS", [])
        self.api_keys = [str(k).strip().replace('"', '').replace("'", "") for k in raw_keys]

    def _get_client(self, index):
        """內部私有方法：建立 Client"""
        return Groq(api_key=self.api_keys[index])

    def _should_rotate(self, error_msg):
        """判斷是否應該切換下一個 Key"""
        error_msg = error_msg.lower()
        # 增加 413, 503, 500 等常見錯誤的自動輪替
        retry_codes = ["429", "rate_limit", "401", "413", "503", "500", "overloaded"]
        return any(code in error_msg for code in retry_codes)

    def generate_qa_content(self, model, messages, temperature=0.3, max_tokens=1024):
        """Llama 模型專用：標準問答"""
        last_error = None           
        for index in range(len(self.api_keys)):
            try:
                client = self._get_client(index)
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_tokens # 建議統一使用 max_completion_tokens
                )                   
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                print(f"[除錯] QA Key #{index+1} 錯誤: {error_msg}")
                if self._should_rotate(error_msg):
                    last_error = e
                    continue 
                raise e           
        raise RuntimeError("所有 QA API Key 的流量都已耗盡或觸發限制。") from last_error

    def generate_materials_content(self, model, messages, temperature=0, max_tokens=2048):
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
                    reasoning_effort="low", # 成功關閉深度推理
                    stream=False
                )                   
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
    return RotationalGroqClient()

model_qa = "llama-3.3-70b-versatile"
model_materials = "openai/gpt-oss-120b"