"""Decrypt an ephemeral X25519 envelope locally and print only the SHA256 checksum."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
LABEL=b'LunexPCControl ephemeral credential v1'

def open_local(key_path:Path,blob_path:Path,output:Path|None=None)->str:
    key=load_pem_private_key(key_path.read_bytes(),password=None)
    doc=json.loads(blob_path.read_bytes())
    if set(doc)!={'v','epk','nonce','data'} or doc['v']!=1:
        raise ValueError('invalid envelope format')
    ephemeral=X25519PublicKey.from_public_bytes(base64.b64decode(doc['epk'],validate=True))
    shared=key.exchange(ephemeral)
    aes_key=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=LABEL).derive(shared)
    plain=AESGCM(aes_key).decrypt(base64.b64decode(doc['nonce'],validate=True),base64.b64decode(doc['data'],validate=True),LABEL)
    if output is not None:
        output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():
            raise FileExistsError('refusing to overwrite existing credential')
        # Never include plaintext in command-line parameters or logs.
        with output.open('xb') as handle:
            handle.write(plain + b'\n')
        os.chmod(output,0o600)
    return hashlib.sha256(plain).hexdigest()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--private',type=Path,required=True)
    p.add_argument('--envelope',type=Path,required=True)
    p.add_argument('--output',type=Path)
    p.add_argument('--quiet',action='store_true')
    a=p.parse_args()
    digest=open_local(a.private,a.envelope,a.output)
    if a.quiet:
        print('Encrypted credential decrypted to a private local file')
    else:
        print('Sealed credential SHA256:',digest)
