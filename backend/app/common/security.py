"""Password hashing (dev plan section 12).

Argon2id via pwdlib — never hand-rolled hashing. The returned hash
string embeds the algorithm, parameters, and a random salt, so
verify_password needs no extra inputs and parameter upgrades can be
detected later via pwdlib's rehash support.
"""

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _hasher.verify(plain_password, password_hash)
