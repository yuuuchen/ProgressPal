# inspect_model.py
import os
import tensorflow as tf
from tensorflow.keras.models import load_model

# 修正你的模型路徑
MODEL_PATH = os.path.join("emotion", "small_label5_aug_best_model_fold_8_v94.74.keras")

def inspect():
    print(f"📂 讀取模型: {MODEL_PATH}")
    
    if not os.path.exists(MODEL_PATH):
        print("❌ 找不到檔案！")
        return

    try:
        # 載入模型
        model = load_model(MODEL_PATH)
        print("✅ 模型載入成功！正在分析輸入層...\n")

        # 1. 直接印出結構表 (最直觀)
        print("="*60)
        model.summary()
        print("="*60)

        # 2. 嘗試解析 Input Shape
        # 有些模型 input_shape 是 list，有些是 tuple，這裡做防呆
        input_shape = model.input_shape
        print(f"\n🔍 原始 Input Shape 屬性: {input_shape}")

        # 判斷通道數
        # 通常 shape 會長這樣 (None, 224, 224, 3) 或 (None, 224, 224, 1)
        # 最後一個數字就是通道數 (Channel)
        
        target_shape = None
        if isinstance(input_shape, list):
            target_shape = input_shape[0] # 取列表第一個
        else:
            target_shape = input_shape
            
        if target_shape:
            channels = target_shape[-1]
            print(f"👉 結論：模型需要 {channels} 通道 (Channels)")
            
            if channels == 3:
                print("💡 建議：這是 RGB 模型，請在 emotion_model.py 開啟「強制轉 RGB」功能。")
            elif channels == 1:
                print("💡 建議：這是灰階模型，請在 emotion_model.py 保持灰階輸入。")
            else:
                print("⚠️ 注意：通道數很特別，請檢查是否為圖片模型。")

    except Exception as e:
        # 這次我們只印出錯誤的前 200 個字，避免洗版
        error_msg = str(e)
        print(f"❌ 分析失敗: {error_msg[:200]}...")

if __name__ == "__main__":
    inspect()