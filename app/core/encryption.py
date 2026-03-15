"""
Field-level encryption for sensitive data at rest.

Uses Fernet symmetric encryption with a key derived from the app's SECRET_KEY.
Applied to ServiceCredentialRecord.token_value and any other sensitive fields.

Usage:
    from app.core.encryption import encrypt_value, decrypt_value

    encrypted = encrypt_value("sk-abc123...")
    original = decrypt_value(encrypted)
"""

import base64
import hashlib
import os
from typing import Optional

from app.core.config import settings
from app.core.logging import logger


def _derive_key(secret: str) -> bytes:
    """
    Derive a 32-byte Fernet key from the application SECRET_KEY.
    Uses SHA-256 hash, base64-encoded for Fernet compatibility.
    """
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


# Lazy-init encryption key
_fernet = None


def _get_fernet():
    """Get or initialize the Fernet cipher instance."""
    global _fernet
    if _fernet is None:
        try:
            from cryptography.fernet import Fernet
            key = _derive_key(settings.secret_key)
            _fernet = Fernet(key)
        except ImportError:
            logger.warning(
                "cryptography package not installed — credential encryption disabled. "
                "Run: pip install cryptography"
            )
            return None
    return _fernet


# Prefix to identify encrypted values (avoids double-encryption)
_ENCRYPTED_PREFIX = "enc::"


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string value. Returns prefixed ciphertext.
    If encryption is unavailable, returns the plaintext unchanged (with warning).
    """
    if not plaintext or plaintext.startswith(_ENCRYPTED_PREFIX):
        return plaintext  # Already encrypted or empty

    fernet = _get_fernet()
    if fernet is None:
        return plaintext  # Graceful degradation

    try:
        encrypted = fernet.encrypt(plaintext.encode())
        return _ENCRYPTED_PREFIX + encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return plaintext  # Don't lose the data


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt a previously encrypted value. Handles both encrypted and
    unencrypted values gracefully (for migration compatibility).
    """
    if not ciphertext:
        return ciphertext

    # If not encrypted, return as-is (backwards compatible with existing unencrypted data)
    if not ciphertext.startswith(_ENCRYPTED_PREFIX):
        return ciphertext

    fernet = _get_fernet()
    if fernet is None:
        logger.warning("Cannot decrypt — cryptography package not available")
        return ciphertext  # Return encrypted value rather than crash

    try:
        encrypted_bytes = ciphertext[len(_ENCRYPTED_PREFIX):].encode()
        return fernet.decrypt(encrypted_bytes).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ciphertext  # Don't crash on bad data


def is_encrypted(value: str) -> bool:
    """Check if a value is already encrypted."""
    return bool(value) and value.startswith(_ENCRYPTED_PREFIX)


def encryption_available() -> bool:
    """Check if encryption is available (cryptography package installed)."""
    return _get_fernet() is not None
