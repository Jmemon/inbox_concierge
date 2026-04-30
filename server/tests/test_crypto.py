import pytest
from app.services.crypto import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "ya29.a0AfH6SMBxxxxxRefreshTokenLikeStuff"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_decrypt_rejects_tampered_ciphertext():
    ciphertext = encrypt("hello")
    tampered = ciphertext[:-2] + "AA"
    with pytest.raises(Exception):
        decrypt(tampered)
