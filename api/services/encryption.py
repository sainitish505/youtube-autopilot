"""
api/services/encryption.py — Fernet symmetric encryption for API keys.

Usage:
    from api.services.encryption import encrypt_key, decrypt_key

    encrypted = encrypt_key("sk-proj-...")
    original  = decrypt_key(encrypted)
"""
import os
import base64
from cryptography.fernet import Fernet


def _get_cipher() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY environment variable not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_key(plaintext: str) -> bytes:
    """Encrypt a plaintext API key. Returns raw bytes for DB BYTEA column."""
    if not plaintext:
        return b""
    return _get_cipher().encrypt(plaintext.encode("utf-8"))


def decrypt_key(ciphertext: bytes) -> str:
    """Decrypt a BYTEA ciphertext back to plaintext. Returns '' if empty."""
    if not ciphertext:
        return ""
    if isinstance(ciphertext, memoryview):
        ciphertext = bytes(ciphertext)
    return _get_cipher().decrypt(ciphertext).decode("utf-8")


def generate_encryption_key() -> str:
    """Generate a new Fernet key string (run once to create ENCRYPTION_KEY)."""
    return Fernet.generate_key().decode()
