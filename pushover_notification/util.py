# -*- coding: utf-8 -*-
import logging
import boto3
import base64

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_KMS = boto3.client('kms')


def kms_decrypt(ciphertext: str) -> bytes:
    """
    Decrypt a value using KMS.

    :param ciphertext: The base64-encoded ciphertext. 
    :return: The plaintext bytestring.
    """
    return _KMS.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext))['Plaintext']


def kms_decrypt_str(ciphertext: str, encoding: str = 'utf-8') -> str:
    """
    Decrypt a piece of text using KMS.

    :param ciphertext: The base64-encoded ciphertext.
    :param encoding: The encoding of the text.
    :return: The plaintext.
    """
    return kms_decrypt(ciphertext).decode(encoding)
