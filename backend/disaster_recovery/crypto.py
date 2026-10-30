# backend/disaster_recovery/crypto.py
#
# Cryptographic envelope and checksum utilities for backup snapshots.
# Uses AES-256 via Fernet (authenticated symmetric encryption) with SHA-256 digests.

import base64
import hashlib
import json
import logging
import secrets
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class BackupCorruptedError(ValueError):
    """Raised when backup payload fails SHA-256 verification or integrity checks."""


class DecryptionError(ValueError):
    """Raised when backup payload cannot be decrypted with the supplied key."""


def generate_backup_key() -> str:
    """Generate a high-entropy base64-encoded 256-bit encryption key."""
    return Fernet.generate_key().decode("utf-8")


def derive_key(secret: str | bytes) -> bytes:
    """Derive a URL-safe base64 32-byte key from a secret string."""
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(digest)


def compute_sha256(data: bytes | str) -> str:
    """Computes hexadecimal SHA-256 digest of data."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def encrypt_payload(data: dict[str, Any] | str, key: str | bytes) -> tuple[str, str]:
    """
    Serializes, encrypts, and returns (ciphertext_b64, sha256_checksum).
    Guarantees authenticated ciphertext and tamper detection.
    """
    raw_str = json.dumps(data, ensure_ascii=False, default=str) if isinstance(data, dict) else str(data)
    derived = derive_key(key) if len(key) != 44 else (key.encode("utf-8") if isinstance(key, str) else key)
    fernet = Fernet(derived)
    ciphertext = fernet.encrypt(raw_str.encode("utf-8")).decode("utf-8")
    checksum = compute_sha256(ciphertext)
    return ciphertext, checksum


def decrypt_payload(ciphertext: str, checksum: str, key: str | bytes) -> Any:
    """
    Verifies checksum, decrypts, and deserializes payload.
    Raises BackupCorruptedError on checksum mismatch, DecryptionError on key failure.
    """
    actual_checksum = compute_sha256(ciphertext)
    if not secrets.compare_digest(actual_checksum, checksum):
        logger.error("Backup integrity failure: checksum mismatch | expected=%s actual=%s",
                     checksum, actual_checksum)
        raise BackupCorruptedError(
            f"Backup payload SHA-256 mismatch (tampered or corrupted). Expected: {checksum}, Got: {actual_checksum}"
        )

    derived = derive_key(key) if len(key) != 44 else (key.encode("utf-8") if isinstance(key, str) else key)
    fernet = Fernet(derived)

    try:
        decrypted_bytes = fernet.decrypt(ciphertext.encode("utf-8"))
        return json.loads(decrypted_bytes.decode("utf-8"))
    except InvalidToken as exc:
        logger.error("Backup decryption failed: invalid encryption key or corrupted block")
        raise DecryptionError("Failed to decrypt backup payload with provided key.") from exc
    except json.JSONDecodeError as exc:
        logger.error("Backup JSON deserialization failed: %s", exc)
        raise BackupCorruptedError(f"Decrypted backup payload is not valid JSON: {exc}") from exc
