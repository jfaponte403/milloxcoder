"""Tests de roundtrip Huffman sobre bytes representativos de varios formatos.

Huffman opera a nivel de bytes: lo que cambia entre formatos es la
distribucion de simbolos. Estos tests verifican que el algoritmo es
correcto y lossless para fuentes con perfiles muy distintos: imagen
comprimida (PNG), imagen no comprimida (JPEG simulado), audio PCM
(WAV), audio comprimido (MP3 simulado), video (MP4 simulado), PDF
y texto UTF-8.
"""

from __future__ import annotations

import json
import struct

import pytest

from huffman import FORMAT_HEADER, decode, encode


# ---------------------------------------------------------------------------
# Fixtures por formato
# ---------------------------------------------------------------------------

@pytest.fixture
def jpeg_bytes() -> bytes:
    """JPEG minimo: SOI + APP0/JFIF + payload sintetico + EOI."""
    soi = b"\xff\xd8"
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    # Payload con distribucion sesgada (como bytes de coeficientes DCT).
    payload = bytes((i * 13 + 7) % 256 for i in range(400))
    eoi = b"\xff\xd9"
    return soi + app0 + payload + eoi


@pytest.fixture
def mp3_bytes() -> bytes:
    """MP3 minimo: cabecera ID3v2 + frames MPEG dummy."""
    id3 = b"ID3\x04\x00\x00\x00\x00\x00\x40"
    pad = b"\x00" * 64
    # Cabeceras de frame MPEG repetidas con datos sinteticos.
    frames = b""
    for i in range(40):
        frames += b"\xff\xfb\x90\x00" + bytes((j * 17 + i) % 256
                                              for j in range(28))
    return id3 + pad + frames


@pytest.fixture
def mp4_bytes() -> bytes:
    """MP4 minimo: ftyp box + mdat box con datos sinteticos."""
    ftyp = (b"\x00\x00\x00\x20" b"ftyp"
            b"isom" b"\x00\x00\x00\x00"
            b"isom" b"avc1" b"mp41")
    mdat_payload = bytes((i * 31 + 5) % 256 for i in range(512))
    mdat = struct.pack(">I", 8 + len(mdat_payload)) + b"mdat" + mdat_payload
    return ftyp + mdat


@pytest.fixture
def pdf_bytes() -> bytes:
    """PDF minimo con cabecera, un objeto y trailer."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
        b"2 0 obj\n<</Type /Pages /Kids [] /Count 0>>\nendobj\n"
        b"3 0 obj\n<</Length 44>>\nstream\n"
        b"BT /F1 12 Tf 100 700 Td (Hola Huffman) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<</Size 4 /Root 1 0 R>>\n"
        b"startxref\n200\n"
        b"%%EOF\n"
    )


@pytest.fixture
def utf8_text_bytes() -> bytes:
    """Texto UTF-8 con caracteres no ASCII para distribucion sesgada."""
    text = (
        "El algoritmo de Huffman asigna codigos prefijo a simbolos segun "
        "su frecuencia. Los simbolos mas comunes reciben codigos cortos; "
        "los raros, largos. Asi se reduce el numero medio de bits por "
        "simbolo, acercandose al limite de Shannon. "
        "Caracteres no ASCII: ñ ç á é í ó ú ¿? ¡! "
    ) * 8
    return text.encode("utf-8")


@pytest.fixture
def gif_bytes() -> bytes:
    """GIF89a minimo con LSD y un par de bloques."""
    header = b"GIF89a"
    lsd = struct.pack("<HH", 4, 4) + b"\x00\x00\x00"
    table = bytes(range(48))  # global color table sintetico
    image_descr = b"\x2c\x00\x00\x00\x00\x04\x00\x04\x00\x00"
    data = b"\x02\x05" + bytes(range(5)) + b"\x00"
    trailer = b"\x3b"
    return header + lsd + table + image_descr + data + trailer


@pytest.fixture
def flac_bytes() -> bytes:
    """FLAC minimo: 'fLaC' + bloque STREAMINFO sintetico."""
    magic = b"fLaC"
    block_header = b"\x80" + b"\x00\x00\x22"
    streaminfo = bytes(34)
    payload = bytes((i * 11 + 3) % 256 for i in range(256))
    return magic + block_header + streaminfo + payload


# ---------------------------------------------------------------------------
# Roundtrip por formato
# ---------------------------------------------------------------------------

class TestFormatRoundtrip:
    """Cada fuente debe sobrevivir encode + decode byte a byte."""

    def test_png_roundtrip(self, png_bytes):
        assert decode(encode(png_bytes)) == png_bytes

    def test_jpeg_roundtrip(self, jpeg_bytes):
        assert decode(encode(jpeg_bytes)) == jpeg_bytes

    def test_gif_roundtrip(self, gif_bytes):
        assert decode(encode(gif_bytes)) == gif_bytes

    def test_wav_roundtrip(self, wav_bytes):
        assert decode(encode(wav_bytes)) == wav_bytes

    def test_mp3_roundtrip(self, mp3_bytes):
        assert decode(encode(mp3_bytes)) == mp3_bytes

    def test_flac_roundtrip(self, flac_bytes):
        assert decode(encode(flac_bytes)) == flac_bytes

    def test_mp4_roundtrip(self, mp4_bytes):
        assert decode(encode(mp4_bytes)) == mp4_bytes

    def test_pdf_roundtrip(self, pdf_bytes):
        assert decode(encode(pdf_bytes)) == pdf_bytes

    def test_text_utf8_roundtrip(self, utf8_text_bytes):
        assert decode(encode(utf8_text_bytes)) == utf8_text_bytes


# ---------------------------------------------------------------------------
# Estructura del codificado por formato
# ---------------------------------------------------------------------------

class TestFormatHeader:
    """El JSON debe llevar original_size y bit_length consistentes."""

    @pytest.fixture(params=[
        "png_bytes", "jpeg_bytes", "gif_bytes", "wav_bytes",
        "mp3_bytes", "flac_bytes", "mp4_bytes", "pdf_bytes",
        "utf8_text_bytes",
    ])
    def sample(self, request):
        return request.getfixturevalue(request.param)

    def test_header_has_original_size(self, sample):
        encoded = encode(sample)
        _, meta_line, _ = encoded.split("\n", 2)
        meta = json.loads(meta_line)
        assert meta["original_size"] == len(sample)

    def test_bit_length_matches_actual_bits(self, sample):
        encoded = encode(sample)
        _, meta_line, bits = encoded.split("\n", 2)
        meta = json.loads(meta_line)
        bits_clean = "".join(bits.split())
        assert meta["bit_length"] == len(bits_clean)

    def test_bitstream_is_only_binary(self, sample):
        encoded = encode(sample)
        bits = encoded.split("\n", 2)[2]
        assert set(bits) <= {"0", "1"}

    def test_starts_with_format_header(self, sample):
        encoded = encode(sample)
        assert encoded.startswith(FORMAT_HEADER + "\n")


# ---------------------------------------------------------------------------
# Caracteristicas de compresion por formato
# ---------------------------------------------------------------------------

class TestFormatCompressionBehavior:
    """Distintas distribuciones de bytes producen distinta efectividad."""

    def test_repetitive_text_compresses_well(self):
        """Texto muy repetido tiene baja entropia: ratio < 70%."""
        data = (b"abcabcabc" * 200)
        encoded = encode(data)
        meta = json.loads(encoded.split("\n", 2)[1])
        ratio = meta["bit_length"] / (len(data) * 8) * 100
        assert ratio < 70, f"Ratio {ratio:.1f}% deberia ser <70% para texto repetitivo"

    def test_uniform_binary_barely_compresses(self):
        """256 simbolos con misma frecuencia: ratio cercano a 100%."""
        data = bytes(range(256)) * 4
        encoded = encode(data)
        meta = json.loads(encoded.split("\n", 2)[1])
        ratio = meta["bit_length"] / (len(data) * 8) * 100
        assert 95 <= ratio <= 105, (
            f"Ratio {ratio:.1f}% deberia ser ~100% para distribucion uniforme"
        )

    def test_single_symbol_is_one_bit_per_symbol(self):
        """Un solo simbolo distinto: 1 bit por byte (12.5% del original)."""
        data = b"X" * 500
        encoded = encode(data)
        meta = json.loads(encoded.split("\n", 2)[1])
        # 1 bit por simbolo de origen
        assert meta["bit_length"] == len(data)
        ratio = meta["bit_length"] / (len(data) * 8) * 100
        assert abs(ratio - 12.5) < 0.5


# ---------------------------------------------------------------------------
# Persistencia: escribir .txt, leerlo, decodificar
# ---------------------------------------------------------------------------

class TestFormatPersistence:
    """Roundtrip completo via disco para cada formato."""

    @pytest.fixture(params=[
        ("imagen.png",      "png_bytes"),
        ("foto.jpg",        "jpeg_bytes"),
        ("animacion.gif",   "gif_bytes"),
        ("audio.wav",       "wav_bytes"),
        ("cancion.mp3",     "mp3_bytes"),
        ("musica.flac",     "flac_bytes"),
        ("video.mp4",       "mp4_bytes"),
        ("documento.pdf",   "pdf_bytes"),
        ("articulo.txt",    "utf8_text_bytes"),
    ])
    def named_sample(self, request):
        filename, fixture_name = request.param
        return filename, request.getfixturevalue(fixture_name)

    def test_save_and_restore_via_txt(self, tmp_path, named_sample):
        original_name, data = named_sample

        encoded = encode(data)
        coded_path = tmp_path / f"coded-{original_name}.txt"
        coded_path.write_text(encoded, encoding="utf-8")

        recovered = decode(coded_path.read_text(encoding="utf-8"))
        restored_path = tmp_path / f"restored-{original_name}"
        restored_path.write_bytes(recovered)

        assert restored_path.read_bytes() == data


# ---------------------------------------------------------------------------
# Sniffer de extension a partir de magic bytes
# ---------------------------------------------------------------------------

class TestSniffExtension:
    """Identifica formato del decodificado cuando no hay loaded_path."""

    @pytest.fixture
    def sniff(self):
        from gui import App
        return App._sniff_extension

    def test_png_is_detected(self, sniff, png_bytes):
        assert sniff(png_bytes) == ".png"

    def test_jpeg_is_detected(self, sniff, jpeg_bytes):
        assert sniff(jpeg_bytes) == ".jpg"

    def test_gif_is_detected(self, sniff, gif_bytes):
        assert sniff(gif_bytes) == ".gif"

    def test_wav_is_detected(self, sniff, wav_bytes):
        assert sniff(wav_bytes) == ".wav"

    def test_mp3_is_detected(self, sniff, mp3_bytes):
        assert sniff(mp3_bytes) == ".mp3"

    def test_flac_is_detected(self, sniff, flac_bytes):
        assert sniff(flac_bytes) == ".flac"

    def test_mp4_is_detected(self, sniff, mp4_bytes):
        assert sniff(mp4_bytes) == ".mp4"

    def test_pdf_is_detected(self, sniff, pdf_bytes):
        assert sniff(pdf_bytes) == ".pdf"

    def test_plain_text_is_detected(self, sniff):
        assert sniff(b"Hola mundo, esto es texto.") == ".txt"

    def test_bmp_is_detected(self, sniff):
        assert sniff(b"BM" + b"\x00" * 100) == ".bmp"

    def test_webp_is_detected(self, sniff):
        assert sniff(b"RIFF\x00\x00\x00\x00WEBP") == ".webp"

    def test_unknown_returns_empty(self, sniff):
        assert sniff(b"\x01\x02\x03\xff" * 10) == ""

    def test_empty_returns_empty(self, sniff):
        assert sniff(b"") == ""


# ---------------------------------------------------------------------------
# Nombre por defecto al guardar el decodificado
# ---------------------------------------------------------------------------

class TestSuggestedDecodedName:
    """save_decoded debe sugerir un nombre util sin que el usuario tipee."""

    @pytest.fixture
    def suggest(self):
        from gui import App
        return App._suggest_decoded_name

    def test_uses_loaded_path_stem_and_ext(self, suggest):
        from pathlib import Path
        name, ext = suggest(Path("xyz.png"), None, b"any bytes")
        assert name == "restored-xyz.png"
        assert ext == ".png"

    def test_preserves_spaces_in_name(self, suggest):
        from pathlib import Path
        name, ext = suggest(Path("mi foto.jpg"), None, None)
        assert name == "restored-mi foto.jpg"
        assert ext == ".jpg"

    def test_path_without_extension(self, suggest):
        from pathlib import Path
        name, ext = suggest(Path("archivo"), None, b"")
        assert name == "restored-archivo"
        assert ext == ""

    def test_recovers_stem_from_coded_prefix(self, suggest, png_bytes):
        from pathlib import Path
        name, ext = suggest(None, Path("coded-xyz.txt"), png_bytes)
        assert name == "restored-xyz.png"
        assert ext == ".png"

    def test_keeps_encoded_stem_if_no_coded_prefix(self, suggest, png_bytes):
        from pathlib import Path
        name, ext = suggest(None, Path("backup.txt"), png_bytes)
        assert name == "restored-backup.png"

    def test_falls_back_to_media_when_pasted(self, suggest, png_bytes):
        name, ext = suggest(None, None, png_bytes)
        assert name == "restored-media.png"
        assert ext == ".png"

    def test_empty_extension_when_unknown_bytes(self, suggest):
        name, ext = suggest(None, None, b"\x01\x02\x03\xff" * 10)
        assert name == "restored-media"
        assert ext == ""

    def test_loaded_path_takes_priority_over_sniffing(self, suggest, png_bytes):
        from pathlib import Path
        # loaded_path .bin gana aunque los bytes sean PNG
        name, ext = suggest(Path("data.bin"), None, png_bytes)
        assert name == "restored-data.bin"
        assert ext == ".bin"

    def test_coded_prefix_with_empty_stem_falls_back(self, suggest, png_bytes):
        from pathlib import Path
        name, ext = suggest(None, Path("coded-.txt"), png_bytes)
        assert name == "restored-media.png"
