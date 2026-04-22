"""Fixtures compartidos para los tests."""

from __future__ import annotations

import os
import struct
import sys
import zlib
from pathlib import Path

import pytest

# Permite importar huffman.py y gui.py desde la raiz del proyecto
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def text_bytes() -> bytes:
    return b"Hola mundo! Huffman en accion con bitstream visible."


@pytest.fixture
def repeated_bytes() -> bytes:
    return b"A" * 500


@pytest.fixture
def binary_bytes() -> bytes:
    return bytes(range(256)) * 4  # 1024 bytes cubriendo todos los simbolos


@pytest.fixture
def png_bytes() -> bytes:
    """Genera un PNG minimalista 2x2 rojo valido."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 2 for _ in range(2))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


@pytest.fixture
def wav_bytes() -> bytes:
    """Genera un WAV minimalista de 100 muestras de silencio a 8 kHz mono."""
    sample_rate = 8000
    num_samples = 100
    data = b"\x00\x00" * num_samples
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
    )
    return header + data


@pytest.fixture
def tmp_media_file(tmp_path: Path, png_bytes: bytes) -> Path:
    p = tmp_path / "fake.png"
    p.write_bytes(png_bytes)
    return p
