
from cryptography.fernet import Fernet
from django.conf import settings


def get_fernet():

    key = settings.DB_CREDENTIAL_ENCRYPTION_KEY

    if not key:
        raise RuntimeError(
            "DB_CREDENTIAL_ENCRYPTION_KEY is missing."
        )

    return Fernet(key.encode())


def encrypt_password(password):

    return get_fernet().encrypt(
        password.encode()
    ).decode()


def decrypt_password(encrypted_password):

    return get_fernet().decrypt(
        encrypted_password.encode()
    ).decode()
