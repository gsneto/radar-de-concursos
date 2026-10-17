"""Validação e armazenamento de imagens de flashcards (Fase 24)."""

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from radar import media
from radar.document_store import migrate_document_schema


def png_bytes(width=20, height=10):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + chunk
            + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF))


def gif_bytes(width=4, height=3):
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00" + b"\x00" * 8


def jpeg_bytes(width=8, height=6):
    sof = struct.pack(">BHHB", 8, height, width, 3) + b"\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    segment = struct.pack(">H", len(sof) + 2) + sof
    return b"\xff\xd8" + b"\xff\xc0" + segment + b"\xff\xd9"


def webp_bytes(width=5, height=4):
    vp8x = bytearray(10)
    vp8x[4:7] = (width - 1).to_bytes(3, "little")
    vp8x[7:10] = (height - 1).to_bytes(3, "little")
    body = b"VP8X" + struct.pack("<I", len(vp8x)) + bytes(vp8x)
    if len(body) % 2:
        body += b"\x00"
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


class DetectTest(unittest.TestCase):
    def test_png_valido(self):
        info = media.detect_image(png_bytes(40, 20))
        self.assertEqual((info["mime"], info["extensao"]), ("image/png", "png"))
        self.assertEqual((info["largura"], info["altura"]), (40, 20))

    def test_gif_valido(self):
        info = media.detect_image(gif_bytes(4, 3))
        self.assertEqual(info["extensao"], "gif")
        self.assertEqual((info["largura"], info["altura"]), (4, 3))

    def test_jpeg_valido(self):
        info = media.detect_image(jpeg_bytes(8, 6))
        self.assertEqual(info["extensao"], "jpg")
        self.assertEqual((info["largura"], info["altura"]), (8, 6))

    def test_webp_valido(self):
        info = media.detect_image(webp_bytes(5, 4))
        self.assertEqual(info["extensao"], "webp")
        self.assertEqual((info["largura"], info["altura"]), (5, 4))

    def test_svg_rejeitado(self):
        with self.assertRaises(media.MediaError):
            media.detect_image(b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')

    def test_texto_rejeitado(self):
        with self.assertRaises(media.MediaError):
            media.detect_image(b"isto nao e uma imagem de verdade")

    def test_vazio_rejeitado(self):
        with self.assertRaises(media.MediaError):
            media.detect_image(b"")

    def test_png_truncado_rejeitado(self):
        with self.assertRaises(media.MediaError):
            media.detect_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)

    def test_dimensao_absurda_rejeitada(self):
        with self.assertRaises(media.MediaError):
            media.detect_image(png_bytes(30000, 10))

    def test_limite_de_bytes(self):
        with self.assertRaises(media.MediaError):
            media.validate_image(png_bytes(), max_bytes=10)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "m.sqlite3")
        migrate_document_schema(self.db)

    def test_guarda_por_hash_e_deduplica(self):
        data = png_bytes()
        first = media.store_image(self.db, data)
        second = media.store_image(self.db, data)
        self.assertEqual(first["sha256"], second["sha256"])
        path = media.media_path(self.db, first["sha256"], first["extensao"])
        self.assertTrue(path.exists())
        self.assertEqual(media.read_media(self.db, first["sha256"], first["extensao"]), data)

    def test_media_dir_fora_do_webroot(self):
        directory = media.media_dir(self.db)
        self.assertEqual(directory.parent, Path(self.db).parent)
        self.assertEqual(directory.name, "estudo-midia")

    def test_hash_invalido_nao_escapa(self):
        self.assertIsNone(media.media_path(self.db, "../../etc/passwd", "png"))
        self.assertIsNone(media.media_path(self.db, "a" * 64, "exe"))
        self.assertIsNone(media.read_media(self.db, "b" * 64, "png"))

    def test_conteudo_invalido_nao_grava(self):
        with self.assertRaises(media.MediaError):
            media.store_image(self.db, b"nao e imagem")


if __name__ == "__main__":
    unittest.main()
