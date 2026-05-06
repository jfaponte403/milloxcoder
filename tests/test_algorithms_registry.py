"""Tests para el registro unificado de algoritmos."""

from __future__ import annotations

import pytest

import algorithms


# ---------- forma del registro ----------

class TestRegistry:
    def test_two_algorithms_registered(self):
        assert set(algorithms.ALGORITHMS.keys()) == {"huffman", "rle"}

    def test_default_is_huffman(self):
        assert algorithms.DEFAULT == "huffman"

    def test_order_covers_all(self):
        assert set(algorithms.ORDER) == set(algorithms.ALGORITHMS.keys())

    def test_get_returns_dataclass(self):
        alg = algorithms.get("huffman")
        assert alg.short_name == "Huffman"
        assert callable(alg.encode)
        assert callable(alg.decode)
        assert alg.has_tree is True

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            algorithms.get("desconocido")

    def test_rle_has_no_tree(self):
        assert algorithms.get("rle").has_tree is False

    def test_headers_are_distinct(self):
        headers = {a.header for a in algorithms.ALGORITHMS.values()}
        assert len(headers) == len(algorithms.ALGORITHMS)


# ---------- deteccion por cabecera ----------

class TestDetect:
    @pytest.mark.parametrize("key", ["huffman", "rle"])
    def test_roundtrip_detection(self, key):
        alg = algorithms.get(key)
        text = alg.encode(b"hola mundo " * 5)
        assert algorithms.detect_from_header(text) == key

    def test_unknown_header_returns_none(self):
        assert algorithms.detect_from_header("BOGUS_v0\n{}\n0101") is None

    def test_empty_string_returns_none(self):
        assert algorithms.detect_from_header("") is None


# ---------- ejecucion uniforme ----------

class TestUniformExecution:
    """Cada algoritmo debe encajar con la misma firma de la GUI:
    encode(data, log=None, on_tree=None) -> str
    decode(text, log=None, on_tree=None) -> bytes
    """

    @pytest.mark.parametrize("key", ["huffman", "rle"])
    def test_roundtrip_via_registry(self, key, text_bytes):
        alg = algorithms.get(key)
        assert alg.decode(alg.encode(text_bytes)) == text_bytes

    @pytest.mark.parametrize("key", ["huffman", "rle"])
    def test_log_callback_works(self, key, text_bytes):
        alg = algorithms.get(key)
        msgs: list[str] = []
        alg.encode(text_bytes, log=msgs.append)
        assert msgs, f"{key} no llamo al log"

    @pytest.mark.parametrize("key", ["huffman", "rle"])
    def test_on_tree_callback_works(self, key, text_bytes):
        alg = algorithms.get(key)
        captured = []
        alg.encode(text_bytes, on_tree=lambda r, c, f: captured.append((r, c, f)))
        assert len(captured) == 1
        root, codes, freqs = captured[0]
        if alg.has_tree:
            assert root is not None
            assert codes is not None
        else:
            # RLE pasa root=None y codes=None pero si entrega freqs
            assert root is None
            assert codes is None
            assert freqs  # frecuencias por byte
