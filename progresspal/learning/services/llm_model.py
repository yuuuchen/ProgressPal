from dotenv import load_dotenv
from groq import Groq
from django.conf import settings

class RotationalGroqClient:
    """自動輪替 Groq API Keys 的 Client"""
    def __init__(self):
        self.api_keys = settings.GROQ_API_KEYS

    def generate_content(self, model, messages, temperature=0.3):
        """
        模擬 Groq 的 chat.completions.create 並加入 Key 輪替邏輯
        """
        last_error = None           
        for index, key in enumerate(self.api_keys):
            try:
                clean_key = str(key).strip().replace('"', '').replace("'", "")
                real_client = Groq(api_key=clean_key)                    
                response = real_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                )                   
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                print(f"[除錯] Groq Key #{index+1} 發生錯誤: {error_msg}")
                # 針對 Groq 的 Rate Limit (429) 或授權問題進行切換
                if "429" in error_msg or "rate_limit" in error_msg or "401" in error_msg:
                    print(f"[警告] Groq Key #{index+1} 失效或流量耗盡，切換下一個 Key...")
                    last_error = e
                    continue 
                else:
                    raise e           
        raise RuntimeError("所有 Groq API Key 的流量都已耗盡。") from last_error

def get_rotational_client():
    return RotationalGroqClient()

model_qa = "llama-3.3-70b-versatile"
model_materials = "openai/gpt-oss-120b"