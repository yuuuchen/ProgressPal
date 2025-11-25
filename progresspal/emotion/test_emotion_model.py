import unittest
import numpy as np
from unittest.mock import patch, MagicMock

# 匯入你要測試的模組
from emotion.emotion_model import predict_emotion, EMOTION_LABELS


class TestEmotionModel(unittest.TestCase):

    def setUp(self):
        """建立一張假影像 (224,224,1) 做測試"""
        self.fake_face = np.random.randint(0, 255, (224, 224, 1), dtype=np.uint8)

    # -----------------------------------------------------
    # 1. 測試：輸入尺寸錯誤
    # -----------------------------------------------------
    def test_invalid_input_shape(self):
        wrong_input = np.zeros((100, 100, 1))

        with self.assertRaises(ValueError):
            predict_emotion(wrong_input)

    # -----------------------------------------------------
    # 2. 測試：模型預測正常（mock model.predict）
    # -----------------------------------------------------
    @patch("emotion.emotion_model.model")
    def test_predict_emotion_success(self, mock_model):
        """
        模擬 model.predict() 回傳固定結果：
        假設模型預測 6 個情緒的 logits，最大值在 index=2（驚訝）
        """
        # 偽造 model.predict() 回傳形式：[[...]]
        mock_model.predict.return_value = np.array([[0.1, 0.05, 0.8, 0.02, 0.015, 0.01]])

        result = predict_emotion(self.fake_face)

        self.assertEqual(result["emotion"], EMOTION_LABELS[2])  # 驚訝
        self.assertAlmostEqual(result["confidence"], 0.8)

    # -----------------------------------------------------
    # 3. 測試：模型未載入時應拋出錯誤
    # -----------------------------------------------------
    @patch("emotion.emotion_model.model", None)
    def test_model_not_loaded(self):
        with self.assertRaises(FileNotFoundError):
            predict_emotion(self.fake_face)


# ---------------------------------------------------------
# 允許直接執行測試
# ---------------------------------------------------------
if __name__ == "__main__":
    unittest.main()