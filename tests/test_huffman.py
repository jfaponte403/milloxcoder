"""Tests unitarios para el modulo huffman."""

from __future__ import annotations

import json

import pytest

from huffman import (
    ALGORITHM_NAME,
    FORMAT_HEADER,
    Node,
    _build_codes,
    _build_frequency_table,
    _build_tree,
    decode,
    encode,
)


# ---------- construccion de tabla de frecuencias ----------

class TestFrequencyTable:
    def test_counts_bytes_correctly(self):
        data = b"aabbc"
        freqs = _build_frequency_table(data)
        assert freqs == {ord("a"): 2, ord("b"): 2, ord("c"): 1}

    def test_empty_data_returns_empty_table(self):
        assert _build_frequency_table(b"") == {}

    def test_covers_all_byte_values(self, binary_bytes):
        freqs = _build_frequency_table(binary_bytes)
        assert len(freqs) == 256
        assert all(f == 4 for f in freqs.values())


# ---------- construccion del arbol ----------

class TestBuildTree:
    def test_single_symbol_tree_is_leaf(self):
        root = _build_tree({65: 10})
        assert root.is_leaf
        assert root.byte == 65

    def test_multi_symbol_tree_freq_sum(self):
        root = _build_tree({1: 3, 2: 5, 3: 7})
        assert root.freq == 15
        assert not root.is_leaf

    def test_tree_is_deterministic(self):
        freqs = {10: 1, 20: 2, 30: 3, 40: 4}
        a = _build_tree(dict(freqs))
        b = _build_tree(dict(freqs))
        assert _build_codes(a) == _build_codes(b)


# ---------- generacion de codigos ----------

class TestBuildCodes:
    def test_single_symbol_gets_one_bit_code(self):
        root = Node(freq=1, order=0, byte=65)
        codes = _build_codes(root)
        assert codes == {65: "0"}

    def test_codes_are_prefix_free(self):
        freqs = {i: i + 1 for i in range(20)}
        root = _build_tree(freqs)
        codes = _build_codes(root)
        sorted_codes = sorted(codes.values(), key=len)
        for i, c1 in enumerate(sorted_codes):
            for c2 in sorted_codes[i + 1:]:
                assert not c2.startswith(c1), f"{c2} tiene prefijo {c1}"

    def test_more_frequent_symbol_has_shorter_code(self):
        root = _build_tree({1: 1, 2: 100})
        codes = _build_codes(root)
        assert len(codes[2]) <= len(codes[1])

    def test_all_symbols_encoded(self):
        freqs = {i: 1 for i in range(50)}
        codes = _build_codes(_build_tree(freqs))
        assert set(codes.keys()) == set(freqs.keys())


# ---------- encode ----------

class TestEncode:
    def test_produces_header(self, text_bytes):
        text = encode(text_bytes)
        assert text.startswith(FORMAT_HEADER)

    def test_output_has_three_lines(self, text_bytes):
        text = encode(text_bytes)
        parts = text.split("\n")
        assert len(parts) == 3

    def test_bitstream_is_only_01(self, text_bytes):
        text = encode(text_bytes)
        bits = text.split("\n")[2]
        assert set(bits) <= {"0", "1"}

    def test_bit_length_matches_header(self, text_bytes):
        text = encode(text_bytes)
        header = json.loads(text.split("\n")[1])
        bits = text.split("\n")[2]
        assert header["bit_length"] == len(bits)

    def test_header_includes_frequencies(self, text_bytes):
        text = encode(text_bytes)
        header = json.loads(text.split("\n")[1])
        assert "frequencies" in header
        assert sum(header["frequencies"].values()) == len(text_bytes)

    def test_header_algorithm_name(self, text_bytes):
        text = encode(text_bytes)
        header = json.loads(text.split("\n")[1])
        assert header["algorithm"] == ALGORITHM_NAME

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            encode(b"")

    def test_log_callback_invoked_with_steps(self, text_bytes):
        messages: list[str] = []
        encode(text_bytes, log=messages.append)
        assert any(m.startswith("Paso 1") for m in messages)
        assert any(m.startswith("Paso 6") for m in messages)
        assert any("completada" in m.lower() for m in messages)

    def test_on_tree_callback_invoked(self, text_bytes):
        captured = {}

        def cb(root, codes, freqs):
            captured["root"] = root
            captured["codes"] = codes
            captured["freqs"] = freqs

        encode(text_bytes, on_tree=cb)
        assert "root" in captured
        assert set(captured["codes"].keys()) == set(captured["freqs"].keys())


# ---------- decode ----------

class TestDecode:
    def test_rejects_wrong_header(self):
        with pytest.raises(ValueError, match="Formato no reconocido"):
            decode("BAD_HEADER\n{}\n0101")

    def test_rejects_non_binary_bitstream(self, text_bytes):
        enc = encode(text_bytes)
        header_line = enc.split("\n")[1]
        corrupted = f"{FORMAT_HEADER}\n{header_line}\n01012X01"
        with pytest.raises(ValueError, match="no binarios"):
            decode(corrupted)

    def test_tolerates_whitespace_in_bitstream(self, text_bytes):
        enc = encode(text_bytes)
        head, meta, bits = enc.split("\n")
        chunked = "\n".join(bits[i:i + 40] for i in range(0, len(bits), 40))
        assert decode(f"{head}\n{meta}\n{chunked}") == text_bytes

    def test_log_callback_invoked(self, text_bytes):
        enc = encode(text_bytes)
        messages: list[str] = []
        decode(enc, log=messages.append)
        assert any(m.startswith("Paso 1") for m in messages)
        assert any("completada" in m.lower() for m in messages)

    def test_on_tree_callback_invoked(self, text_bytes):
        enc = encode(text_bytes)
        captured = {}
        decode(enc, on_tree=lambda r, c, f: captured.update(root=r, codes=c, freqs=f))
        assert "root" in captured


# ---------- roundtrip: caso basico del usuario ----------

class TestRoundtrip:
    @pytest.mark.parametrize("data", [
        b"a",
        b"ab",
        b"hello world",
        b"\x00\x01\x02\x03",
        bytes(range(256)),
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

    def test_roundtrip_large_random(self):
        import random
        random.seed(42)
        data = bytes(random.randint(0, 255) for _ in range(5000))
        assert decode(encode(data)) == data


# ---------- compresion efectiva ----------

class TestCompression:
    def test_repeated_data_compresses(self, repeated_bytes):
        enc = encode(repeated_bytes)
        bits = enc.split("\n")[2]
        # 500 'A' deben caber en muchos menos que 500*8 bits
        assert len(bits) < len(repeated_bytes) * 8

    def test_single_symbol_uses_one_bit_per_byte(self):
        data = b"Z" * 64
        enc = encode(data)
        bits = enc.split("\n")[2]
        assert len(bits) == 64  # 1 bit por simbolo
