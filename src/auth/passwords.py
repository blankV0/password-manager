"""
Password hashing with Argon2id.

Argon2id is the winner of the Password Hashing Competition and the
current OWASP recommendation.  Parameters chosen here
(``time_cost=3``, ``memory_cost=64 MiB``, ``parallelism=4``) balance
security against the latency budget of interactive login.

The module also exposes :func:`needs_rehash` so that the auth service
can transparently upgrade hashes when parameters are tuned.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)



def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False



def needs_rehash(password_hash: str) -> bool:
    return password_hasher.check_needs_rehash(password_hash)
