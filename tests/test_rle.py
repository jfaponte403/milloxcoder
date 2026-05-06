"""Tests para el modulo rle."""

from __future__ import annotations

import json

import pytest

from rle import (
    ALGORITHM_NAME,
    FORMAT_HEADER,
    MAX_RUN,
    _runs,
    decode,
    encode,
)


# ---------- runs ----------

class TestRuns:
    def test_empty_data(self):
        assert list(_runs(b"")) == []

    def test_single_byte(self):
        assert list(_runs(b"A")) == [(ord("A"), 1)]

    def test_simple_run(self):
        assert list(_runs(b"AAA")) == [(ord("A"), 3)]

    def test_alternating(self):
        assert list(_runs(b"ABAB")) == [
            (ord("A"), 1), (ord("B"), 1), (ord("A"), 1), (ord("B"), 1),
        ]

    def test_run_caps_at_max(self):
        # 300 As -> dos tokens: 255, 45
        runs = list(_runs(b"A" * 300))
        assert runs == [(ord("A"), MAX_RUN), (ord("A"), 300 - MAX_RUN)]

    def test_run_count_total_matches_input(self):
        data = b"AAAABBBBCC" * 50
        total = sum(c for _, c in _runs(data))
        assert total == len(data)


# ---------- encode ----------

class TestEncode:
    def test_produces_header(self):
        text = encode(b"AAAA")
        assert text.startswith(FORMAT_HEADER)

    def test_output_has_three_lines(self):
        text = encode(b"AAABBB")
        assert len(text.split("\n")) == 3

    def test_header_algorithm_name(self):
        header = json.loads(encode(b"X").split("\n")[1])
        assert header["algorithm"] == ALGORITHM_NAME

    def test_header_run_count(self):
        # AABB -> 2 runs
        header = json.loads(encode(b"AABB").split("\n")[1])
        assert header["run_count"] == 2

    def test_body_uses_hex_uppercase(self):
        # 0xff = 255, asi que el byte debe aparecer como FF
        text = encode(b"\xff\xff\xff")
        body = text.split("\n")[2]
        assert "FF" in body

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            encode(b"")

    def test_log_callback_invoked(self):
        messages: list[str] = []
        encode(b"AAAA", log=messages.append)
        assert any(m.startswith("Paso 1") for m in messages)
        assert any("completada" in m.lower() for m in messages)


# ---------- decode ----------

class TestDecode:
    def test_rejects_wrong_header(self):
        with pytest.raises(ValueError, match="Formato no reconocido"):
            decode("HUFFMAN_v1\n{}\n3*41")

    def test_rejects_token_without_separator(self):
        bad = f"{FORMAT_HEADER}\n" + json.dumps({"original_size": 1}) + "\nABC"
        with pytest.raises(ValueError, match="separador"):
            decode(bad)

    def test_rejects_count_zero(self):
        bad = f"{FORMAT_HEADER}\n" + json.dumps({"original_size": 0}) + "\n0*41"
        with pytest.raises(ValueError, match="rango"):
            decode(bad)

    def test_rejects_count_above_max(self):
        bad = f"{FORMAT_HEADER}\n" + json.dumps({"original_size": 256}) + f"\n{MAX_RUN + 1}*41"
        with pytest.raises(ValueError, match="rango"):
            decode(bad)

    def test_rejects_byte_out_of_range(self):
        bad = f"{FORMAT_HEADER}\n" + json.dumps({"original_size": 1}) + "\n1*100"
        with pytest.raises(ValueError, match="rango"):
            decode(bad)


# ---------- roundtrip ----------

class TestRoundtrip:
    @pytest.mark.parametrize("data", [
        b"a",
        b"AB",
        b"AAABBB",
        b"\x00\x01\x02\x03",
        bytes(range(256)),
        b"X" * 300,  # fuerza split de run
        b"X" * MAX_RUN,
        b"X" * (MAX_RUN + 1),
    ])
    def test_roundtrip_various(self, data):
        assert decode(encode(data)) == data

    def test_roundtrip_text(self, text_bytes):
        assert decode(encode(text_bytes)) == text_bytes

    def test_roundtrip_repeated(self, repeated_bytes):
        assert decode(encode(repeated_bytes)) == repeated_bytes

    def test_roundtrip_full_byte_range(self, binary_bytes):
        assert decode(encode(binary_bytes)) == binary_bytes

    def test_roundtrip_png(self, png_bytes):
        assert decode(encode(png_bytes)) == png_bytes

    def test_roundtrip_wav(self, wav_bytes):
        assert decode(encode(wav_bytes)) == wav_bytes


# ---------- compresion / expansion ----------

class TestCompression:
    def test_repeated_data_compresses(self, repeated_bytes):
        # 500 As -> body deberia ser mucho menor que 500 bytes en chars
        text = encode(repeated_bytes)
        body = text.split("\n")[2]
        # 500/255 = ~2 runs, cada uno ~7 chars: muchisimo menos que 500
        assert len(body) < 50

    def test_random_data_can_expand(self):
        # Datos sin runs largos: RLE expande
        import random
        random.seed(7)
        data = bytes(random.randint(0, 255) for _ in range(200))
        text = encode(data)
        # El body suele ser ~6 chars por byte de entrada cuando no hay runs.
        body = text.split("\n")[2]
        assert len(body) > len(data)
