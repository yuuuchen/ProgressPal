"""
使用者 Groq API Key 的加解密（Fernet 對稱加密），Session 只存密文。

金鑰來源：
- 優先使用 .env 的 FERNET_ENCRYPTION_KEY（以 Fernet.generate_key() 產生，正式環境 / Docker 應設定）
- 未設定時改用 SECRET_KEY 衍生出的金鑰，讓本機開發不設定也能運作

注意：更換金鑰後舊的密文將無法解開（decrypt 回傳空字串），使用者需要重新登入並輸入 API Key。
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    configured = getattr(settings, "FERNET_ENCRYPTION_KEY", "")
    if configured:
        return Fernet(configured.encode())
    digest = hashlib.sha256(("progresspal-groq-api-key:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext):
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.strip().encode()).decode()


def decrypt(token):
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""
