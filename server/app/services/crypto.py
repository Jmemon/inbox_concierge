from cryptography.fernet import Fernet
from app.config import get_settings


_fernet: Fernet | None = None


def _get() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_settings().encryption_key.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    return _get().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get().decrypt(ciphertext.encode()).decode()
