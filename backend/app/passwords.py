"""Salted password storage; no plaintext credentials in new or migrated rows."""
import hashlib
import secrets

PREFIX = "pbkdf2_sha256$"
ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), ITERATIONS).hex()
    return f"{PREFIX}{ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), int(iterations)).hex()
        return secrets.compare_digest(actual, expected)
    except (AttributeError, ValueError):
        return False
