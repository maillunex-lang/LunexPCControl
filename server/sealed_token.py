"""Envelope encrypt short-lived device credentials to an enrolled SSH Ed25519 key.

Ed25519 keys are signing keys, not encryption keys. We intentionally DO NOT
silently convert them to X25519 here: mixing signing and ECDH identities makes
key lifecycle and protocol review harder. Use a separate X25519 encryption key.
"""
from __future__ import annotations
import base64
import json
import os
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey, X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

LABEL = b"LunexPCControl ephemeral credential v1"


def seal(public_key: bytes, plaintext: bytes) -> bytes:
    if len(public_key) != 32 or not 24 <= len(plaintext) <= 512:
        raise ValueError("invalid public key or secret length")
    ephemeral = X25519PrivateKey.generate()
    shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(public_key))
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=LABEL).derive(shared)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, LABEL)
    doc = {"v":1,"epk":base64.b64encode(ephemeral.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),
           "nonce":base64.b64encode(nonce).decode(),"data":base64.b64encode(ciphertext).decode()}
    return json.dumps(doc,separators=(",",":")).encode("ascii")


def open_sealed(private_key: X25519PrivateKey, blob: bytes) -> bytes:
    if len(blob) > 2048: raise ValueError("oversized envelope")
    doc = json.loads(blob)
    if set(doc) != {"v","epk","nonce","data"} or doc["v"] != 1:
        raise ValueError("invalid envelope")
    epk = base64.b64decode(doc["epk"],validate=True)
    nonce = base64.b64decode(doc["nonce"],validate=True)
    ciphertext = base64.b64decode(doc["data"],validate=True)
    if len(epk) != 32 or len(nonce) != 12:
        raise ValueError("invalid envelope fields")
    shared = private_key.exchange(X25519PublicKey.from_public_bytes(epk))
    key = HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=LABEL).derive(shared)
    return AESGCM(key).decrypt(nonce,ciphertext,LABEL)
