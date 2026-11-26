"""Provision a separate local X25519 key for short-lived credential envelopes."""
import argparse
import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption,load_pem_private_key


def create(folder: Path, export: Path):
    folder.mkdir(parents=True,exist_ok=True)
    private=folder/'seal-private.pem'
    public=folder/'seal-public.key'
    if private.exists() != public.exists():
        raise RuntimeError('incomplete keypair, refusing overwrite')
    if not private.exists():
        key=X25519PrivateKey.generate()
        with private.open('xb') as out:
            out.write(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
        os.chmod(private,0o600)
        with public.open('xb') as out:
            out.write(base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)))
    else:
        key=load_pem_private_key(private.read_bytes(),password=None)
        derived=base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
        if public.read_bytes()!=derived:raise RuntimeError('keypair mismatch')
    blob=public.read_bytes()
    if export.exists():
        if export.read_bytes()!=blob: raise RuntimeError('existing export differs')
    else:
        export.write_bytes(blob)
    print('Device sealing public key exported; private key remains local')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--folder',required=True,type=Path)
    p.add_argument('--export',required=True,type=Path)
    a=p.parse_args()
    create(a.folder,a.export)
