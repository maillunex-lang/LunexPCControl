import base64
import json
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

from server.screen_history import ScreenHistory, extract_pngs

def sample_png():
    def chunk(kind, data):
        blob = kind+data
        return struct.pack('>I',len(data))+blob+struct.pack('>I',zlib.crc32(blob)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
            + chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00'))
            + chunk(b'IEND',b''))

def response(png=None, error=False):
    png=png or sample_png()
    return json.dumps({'jsonrpc':'2.0','id':1,'result':{
        'isError':error,
        'content':[{'type':'image','mimeType':'image/png',
                    'data':base64.b64encode(png).decode()}]}}).encode()

class ScreenHistoryTests(unittest.TestCase):
    def test_extract_authenticated_png_format_only(self):
        data=response()
        self.assertEqual(extract_pngs(data),[sample_png()])
        self.assertEqual(extract_pngs(response(error=True)),[])
        self.assertEqual(extract_pngs(b'[]'),[])
        self.assertEqual(extract_pngs(b'invalid'),[])
        self.assertEqual(extract_pngs(response(b'not PNG')),[])
        self.assertEqual(extract_pngs(response(b'\x89PNG\r\n\x1a\n')),[])

    def test_disabled_by_default_then_encrypted_and_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            storage=ScreenHistory(Path(folder)/'captures')
            self.assertFalse(storage.settings()['enabled'])
            self.assertEqual(storage.capture('pc',response()),0)
            self.assertEqual(storage.list(),[])
            storage.configure(24,50)
            self.assertEqual(storage.capture('pc',response()),1)
            item=storage.list()[0]
            self.assertEqual(item['device'],'pc')
            self.assertEqual(storage.image(item['id']),sample_png())
            encrypted=(storage.folder/(item['id']+'.enc'))
            self.assertNotIn(sample_png(), encrypted.read_bytes())
            self.assertEqual(encrypted.stat().st_mode&0o777,0o600)
            self.assertEqual(storage.key_path.stat().st_mode&0o777,0o600)
            self.assertEqual(storage.db_path.stat().st_mode&0o777,0o600)
            self.assertEqual(storage.image('something-else'),None)
            storage.configure(0)
            self.assertEqual(storage.list(),[])
            self.assertFalse(encrypted.exists())

    def test_last_only_and_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            storage=ScreenHistory(Path(folder)/'captures')
            storage.configure(24,1)
            self.assertEqual(storage.capture('pc',response()),1)
            self.assertEqual(storage.capture('pc',response()),1)
            self.assertEqual(len(storage.list()),1)
            with storage._db() as db:
                db.execute('UPDATE images SET created=?',(time.time()-25*3600,))
            self.assertEqual(storage.list(),[])
            for invalid in (-1, 2, '24', True, 999):
                with self.subTest(value=invalid),self.assertRaises(ValueError):
                    storage.configure(invalid)
            with self.assertRaises(ValueError):
                storage.configure(24,999)
            self.assertEqual(storage.capture('../bad',response()),0)

    def test_persistent_settings_and_global_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            location=Path(folder)/'screens'
            initial=ScreenHistory(location)
            initial.configure(24,50)
            reopened=ScreenHistory(location)
            self.assertEqual(reopened.settings()['retention_hours'],24)
            item_size=len(sample_png())
            with patch('server.screen_history.MAX_STORED_BYTES', item_size+1):
                reopened.capture('pc',response())
                reopened.capture('pc',response())
                self.assertEqual(len(reopened.list()),1)
            reopened.configure(0)
            self.assertFalse(list(location.glob('*.enc')))

    def test_invalid_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            parent=Path(folder)/'captures'
            parent.mkdir(mode=0o755)
            with self.assertRaises(PermissionError):
                ScreenHistory(parent)

    def test_modified_ciphertext_is_not_decoded(self):
        with tempfile.TemporaryDirectory() as folder:
            storage=ScreenHistory(Path(folder)/'captures')
            storage.configure(24,50)
            storage.capture('pc',response())
            item=storage.list()[0]
            path=storage.folder/(item['id']+'.enc')
            encrypted=bytearray(path.read_bytes())
            encrypted[-1]^=1
            path.write_bytes(encrypted)
            with self.assertRaises(Exception):
                storage.image(item['id'])

if __name__=='__main__':
    unittest.main()
