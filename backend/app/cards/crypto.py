"""Card encryption with AES-256-GCM (R4).

The key is CARD_ENCRYPTION_KEY: 32 bytes, base64. Make one with
`openssl rand -base64 32` and put it in Secret app-credentials. Every write uses
a fresh 12-byte nonce. The attendee ID is the associated data, so a ciphertext
copied to another attendee's row does not decrypt.
"""

import base64
import json
import logging
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger("affinity.cards")
_DEV_KEY = b"affinity-dev-card-key-32-bytes!!"  # local development only


def _key() -> bytes:
    raw = os.getenv("CARD_ENCRYPTION_KEY")
    if not raw:
        log.warning("CARD_ENCRYPTION_KEY is not set: using the development key")
        return _DEV_KEY
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("CARD_ENCRYPTION_KEY must be 32 bytes, base64-encoded")
    return key


def encrypt(attendee_id: str, card: dict) -> tuple[bytes, bytes]:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, json.dumps(card).encode(), attendee_id.encode())
    return ciphertext, nonce


def decrypt(attendee_id: str, ciphertext: bytes, nonce: bytes) -> dict:
    """Raises cryptography.exceptions.InvalidTag if anything was changed."""
    return json.loads(AESGCM(_key()).decrypt(nonce, ciphertext, attendee_id.encode()))
