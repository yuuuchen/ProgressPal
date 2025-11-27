import unittest
import numpy as np
from unittest.mock import patch
from emotion.emotion_model import predict_emotion


class TestEmotionModel(unittest.TestCase):

    def setUp(self):
        # 符合 shape (1,224,224,1)
        self.fake_face = np.zeros((1, 224, 224, 1), dtype=np.float32)

    @patch("emotion.emotion_model.model")
    def test_invalid_input_shape(self, mock_model):
        """
        如果輸入影像 shape 不是 (1,224,224,1)，應該拋出 ValueError
        """
        mock_model.predict.return_value = np.zeros((1, 6))
        
        wrong_input = np.zeros((224, 224, 1))  
        
        with self.assertRaises(ValueError):
            predict_emotion(wrong_input)

    @patch("emotion.emotion_model.model")
    def test_predict_emotion_success(self, mock_model):
        """
        模擬 model.predict() 回傳固定結果，測試 predict_emotion 是否正確回傳 emotion 與 confidence
        """
        # 模擬模型預測結果：第 2 類（index=2）最高
        mock_model.predict.return_value = np.array([[0.1, 0.2, 0.5, 0.1, 0.05, 0.05]])

        result = predict_emotion(self.fake_face)

        self.assertEqual(result["emotion"], "驚訝")  # EMOTION_LABELS[2]
        self.assertAlmostEqual(result["confidence"], 0.5)

    @patch("emotion.emotion_model.model")
    def test_model_predict_called_once(self, mock_model):
        """
        確認 model.predict 是否有被呼叫一次
        """
        mock_model.predict.return_value = np.array([[0.3, 0.1, 0.2, 0.1, 0.2, 0.1]])

        predict_emotion(self.fake_face)

        mock_model.predict.assert_called_once()


if __name__ == "__main__":
    unittest.main()
