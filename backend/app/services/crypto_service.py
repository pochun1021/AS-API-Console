import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import ApiError


class CryptoService:
    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("API_KEY_ENCRYPTION_SECRET is required")
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self.fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ApiError("KEY_DECRYPT_FAILED", "key decrypt failed", 500) from exc
