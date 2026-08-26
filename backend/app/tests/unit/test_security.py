"""Unit tests for password hashing."""

from app.common.security import hash_password, verify_password


def test_hash_is_not_the_plaintext():
    assert hash_password("correct horse battery staple") != "correct horse battery staple"


def test_correct_password_verifies():
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed) is True


def test_wrong_password_fails():
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret", hashed) is False
    assert verify_password("", hashed) is False


def test_same_password_hashes_differently_each_time():
    # A random salt per hash means identical passwords never share a
    # hash, so a leaked database can't be attacked with one lookup table.
    assert hash_password("same password") != hash_password("same password")


def test_hash_declares_argon2():
    assert hash_password("x").startswith("$argon2")
