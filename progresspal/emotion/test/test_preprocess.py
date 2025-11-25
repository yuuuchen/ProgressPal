# emotion/test/test_preprocess.py
import os
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from emotion.services.preprocess import preprocess_frame, InvalidImageError, NoFaceDetectedError
TEST_IMG_DIR = "emotion/tests/images"

class PreprocessTests(TestCase):

    def load_test_img(self, filename):
        """讀取本地測試圖片，模擬 Django 上傳行為"""
        path = os.path.join(TEST_IMG_DIR, filename)
        with open(path, "rb") as f:
            return SimpleUploadedFile(filename, f.read(), content_type="image/jpeg")

    def test_normal_face(self):
        file = self.load_test_img("face.jpg")
        result = preprocess_frame(file)
        self.assertEqual(result.shape, (1, 224, 224, 1))

    def test_no_face(self):
        file = self.load_test_img("no_face.jpg")
        with self.assertRaises(NoFaceDetectedError):
            preprocess_frame(file)

    def test_multi_face(self):
        file = self.load_test_img("multi_face.jpg")
        # MediaPipe 預設只回傳最高 confidence 的一臉，因此應該仍然正常回傳
        result = preprocess_frame(file)
        self.assertEqual(result.shape, (1, 224, 224, 1))

    def test_side_face(self):
        file = self.load_test_img("side_face.jpg")
        # 側臉 MediaPipe 可能成功也可能失敗 → 都可接受，但不應拋 InvalidImageError
        try:
            result = preprocess_frame(file)
            self.assertEqual(result.shape, (1, 224, 224, 1))
        except NoFaceDetectedError:
            pass

    def test_blurry_face(self):
        file = self.load_test_img("blurry_face.jpg")
        # 同側臉：失敗時 NoFaceDetectedError，不應其他 error
        try:
            result = preprocess_frame(file)
            self.assertEqual(result.shape, (1, 224, 224, 1))
        except NoFaceDetectedError:
            pass
