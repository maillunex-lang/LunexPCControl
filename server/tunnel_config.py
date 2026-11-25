"""Generate a restricted OpenSSH authorized_keys entry for a device."""
import base64
import re
import struct

def authorized_key(public_key: str, port: int) -> str:
    if type(port) is not int or not 20000 <= port <= 29999:
        raise ValueError('port outside device range')
    fields = public_key.strip().split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519' or not re.fullmatch(r'[A-Za-z0-9+/=]+', fields[1]):
        raise ValueError('expected Ed25519 public key')
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except ValueError as exc:
        raise ValueError('invalid key encoding') from exc
    prefix = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32)
    if not blob.startswith(prefix) or len(blob) != len(prefix) + 32:
        raise ValueError('invalid key blob')
    return f'restrict,port-forwarding,permitlisten="127.0.0.1:{port}",command="/bin/false" ssh-ed25519 {fields[1]}'
