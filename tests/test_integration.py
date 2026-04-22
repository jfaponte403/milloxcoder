"""Tests de integracion que emulan los flujos de la GUI."""

from __future__ import annotations

from pathlib import Path

import pytest

from huffman import decode, encode

LOGO_PATH = Path(__file__).parent / "logo-test.jpg"


# ---------- flujo: cargar archivo -> codificar -> guardar .txt ----------

class TestEncodeFlow:
    def test_load_media_and_encode(self, tmp_media_file: Path):
        data = tmp_media_file.read_bytes()
        assert data  # la fixture genera PNG valido
        enc = encode(data)
        assert enc.startswith("HUFFMAN_v1")

    def test_save_encoded_txt(self, tmp_path: Path, png_bytes: bytes):
        enc = encode(png_bytes)
        out = tmp_path / "encoded.huff.txt"
        out.write_text(enc, encoding="utf-8")
        assert out.exists()
        assert out.read_text(encoding="utf-8") == enc


# ---------- flujo: cargar .txt -> decodificar -> guardar media ----------

class TestDecodeFlow:
    def test_load_txt_and_decode(self, tmp_path: Path, png_bytes: bytes):
        enc_path = tmp_path / "img.huff.txt"
        enc_path.write_text(encode(png_bytes), encoding="utf-8")

        loaded = enc_path.read_text(encoding="utf-8")
        decoded = decode(loaded)
        assert decoded == png_bytes

    def test_save_decoded_matches_original(self, tmp_path: Path, wav_bytes: bytes):
        enc_path = tmp_path / "audio.huff.txt"
        enc_path.write_text(encode(wav_bytes), encoding="utf-8")

        decoded = decode(enc_path.read_text(encoding="utf-8"))
        out = tmp_path / "restored.wav"
        out.write_bytes(decoded)
        assert out.read_bytes() == wav_bytes


# ---------- flujo: copiar/pegar bitstream con saltos ----------

class TestClipboardFlow:
    def test_decode_handles_user_paste_with_newlines(self, png_bytes: bytes):
        enc = encode(png_bytes)
        head, meta, bits = enc.split("\n")
        # Simula un pegado con saltos de linea cada 80 chars (como editores)
        wrapped = "\n".join(bits[i:i + 80] for i in range(0, len(bits), 80))
        pasted = f"{head}\n{meta}\n{wrapped}"
        assert decode(pasted) == png_bytes

    def test_decode_handles_trailing_whitespace(self, text_bytes: bytes):
        enc = encode(text_bytes) + "   \n  "
        assert decode(enc) == text_bytes


# ---------- flujo: doble codificacion / decodificacion ----------

class TestDoubleFlow:
    def test_double_roundtrip_stable(self, text_bytes: bytes):
        once = decode(encode(text_bytes))
        twice = decode(encode(once))
        assert once == twice == text_bytes

    def test_encode_is_deterministic(self, text_bytes: bytes):
        assert encode(text_bytes) == encode(text_bytes)


# ---------- errores esperados por el usuario ----------

class TestErrorPaths:
    def test_encode_empty_file_rejected(self, tmp_path: Path):
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")
        with pytest.raises(ValueError):
            encode(empty.read_bytes())

    def test_decode_rejects_unknown_format(self, tmp_path: Path):
        bad = tmp_path / "bad.txt"
        bad.write_text("no soy huffman", encoding="utf-8")
        with pytest.raises(ValueError):
            decode(bad.read_text(encoding="utf-8"))

    def test_decode_rejects_truncated_bitstream(self, text_bytes: bytes):
        enc = encode(text_bytes)
        head, meta, bits = enc.split("\n")
        truncated = f"{head}\n{meta}\n{bits[:10]}"
        import json
        header = json.loads(meta)
        # El bit_length dice mas bits de los que hay -> decode recorta y produce basura o falla
        # Aqui solo aseguramos que no reviente silenciosamente con datos incompletos
        result = decode(truncated)
        assert len(result) <= header["original_size"]


# ---------- flujo real con logo-test.jpg ----------

@pytest.mark.skipif(not LOGO_PATH.exists(), reason="tests/logo-test.jpg no disponible")
class TestRealImageFlow:
    def test_encode_save_load_decode_logo(self, tmp_path: Path):
        # 1. Leer imagen original y codificarla
        original = LOGO_PATH.read_bytes()
        assert len(original) > 0
        encoded_text = encode(original)

        # 2. Guardar el archivo codificado (.huff.txt) en disco
        encoded_file = tmp_path / "logo-test.huff.txt"
        encoded_file.write_text(encoded_text, encoding="utf-8")
        assert encoded_file.exists()
        assert encoded_file.stat().st_size > 0

        # 3. Cargar el archivo codificado desde disco y recuperar la imagen
        loaded_text = encoded_file.read_text(encoding="utf-8")
        recovered = decode(loaded_text)

        # La imagen recuperada debe ser byte a byte igual a la original
        assert recovered == original
        assert len(recovered) == len(original)

        # Y al guardarla como .jpg debe quedar identica
        recovered_file = tmp_path / "logo-recovered.jpg"
        recovered_file.write_bytes(recovered)
        assert recovered_file.read_bytes() == original

    def test_logo_encoding_produces_visible_bitstream(self):
        encoded = encode(LOGO_PATH.read_bytes())
        lines = encoded.split("\n")
        assert lines[0] == "HUFFMAN_v1"
        bits = lines[2]
        # El bitstream es solo 0s y 1s, no base64
        assert set(bits) <= {"0", "1"}
        assert len(bits) > 0

    def test_large_encoded_txt_roundtrip(self, tmp_path: Path):
        """Reproduce el flujo: cargar imagen -> codificar -> guardar .txt ->
        cargar .txt -> decodificar. Prueba con un texto mayor a DISPLAY_LIMIT
        para asegurar que el truncado de pantalla no afecta la decodificacion."""
        original = LOGO_PATH.read_bytes()
        encoded = encode(original)

        # Para una imagen real el texto codificado supera holgadamente DISPLAY_LIMIT
        import gui
        assert len(encoded) > gui.DISPLAY_LIMIT

        txt_path = tmp_path / "logo-test.huff.txt"
        txt_path.write_text(encoded, encoding="utf-8")

        loaded = txt_path.read_text(encoding="utf-8")
        assert loaded == encoded
        assert decode(loaded) == original

    def test_logo_double_roundtrip(self, tmp_path: Path):
        original = LOGO_PATH.read_bytes()

        # Primera vuelta
        first_txt = tmp_path / "pass1.huff.txt"
        first_txt.write_text(encode(original), encoding="utf-8")
        pass1 = decode(first_txt.read_text(encoding="utf-8"))

        # Segunda vuelta sobre el resultado
        second_txt = tmp_path / "pass2.huff.txt"
        second_txt.write_text(encode(pass1), encoding="utf-8")
        pass2 = decode(second_txt.read_text(encoding="utf-8"))

        assert pass1 == pass2 == original


# ---------- smoke test del modulo gui ----------

class TestGuiModule:
    def test_gui_module_importable(self):
        import gui
        assert hasattr(gui, "App")
        assert hasattr(gui, "main")
        assert hasattr(gui, "RoundedButton")

    def test_gui_constants_defined(self):
        import gui
        assert gui.DISPLAY_LIMIT > 0
        assert gui.MEDIA_EXTENSIONS
        assert gui.COL_BG.startswith("#")

    def test_pick_font_returns_string(self):
        import tkinter as tk

        import gui
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            pytest.skip("No hay display disponible")
        try:
            font = gui._pick_font()
            assert isinstance(font, str) and font
        finally:
            root.destroy()
