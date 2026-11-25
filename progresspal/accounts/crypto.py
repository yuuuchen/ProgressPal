"""
使用者 Groq API Key 的加解密。

以 SECRET_KEY 衍生出 Fernet 金鑰做對稱加密，資料庫只存密文。
注意：更換 SECRET_KEY 後舊的密文將無法解開（decrypt 回傳空字串），使用者需要重新設定 API Key。
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    digest = hashlib.sha256(("progresspal-groq-api-key:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext):
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token):
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""
