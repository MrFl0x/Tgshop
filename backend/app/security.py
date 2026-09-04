"""
Хеширование паролей редакторов (AdminUser.password_hash). Сделано на stdlib
(hashlib.pbkdf2_hmac), а не на passlib/bcrypt — чтобы не тащить лишнюю
зависимость и не словить их известные проблемы совместимости версий
(passlib давно не обновлялся и ломается с новыми bcrypt). Формат хранения —
как в Django: "pbkdf2_sha256$итерации$соль_hex$хеш_hex".
"""
import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 260_000  # ориентир OWASP на 2024-2025 для PBKDF2-SHA256


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations_str, salt_hex, digest_hex = encoded.split("$")
        if algo != _ALGO:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
