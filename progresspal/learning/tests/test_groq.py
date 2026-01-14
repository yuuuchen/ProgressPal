import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv() # 確保讀取了 .env 檔案

api_key = os.getenv("GROQ_API_KEY1")
print(f"目前讀取到的 Key 為: {api_key}") # 檢查這裡印出來的是否為正確的 Key

if api_key:
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "測試"}]
        )
        print("連線成功！")
    except Exception as e:
        print(f"連線失敗，錯誤原因：{e}")
else:
    print("錯誤：抓不到環境變數中的 API Key")