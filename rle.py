"""Run-Length Encoding sobre bytes crudos, con log paso a paso.

Codifica secuencias consecutivas del mismo byte como pares (cuenta, byte).
A diferencia de Huffman/Shannon-Fano, no usa entropia ni un arbol: solo
explota repeticiones contiguas. Brilla en datos con runs largos (imagenes
plano, audio en silencio, texto repetitivo) y se hunde en datos aleatorios,
donde puede expandir el archivo.

Wire format:
    RLE_v1\n
    {"algorithm":"...","version":1,"original_size":N,"run_count":K}\n
    NN*BB NN*BB NN*BB ...

Cada token es 'cuenta*byte_hex' (cuenta decimal entre 1 y 255, byte como
dos digitos hex en mayusculas), separados por espacios.
"""

from __future__ import annotations

import json
from typing import Callable, Iterator, Optional

ALGORITHM_NAME = "Run-Length Encoding"
FORMAT_HEADER = "RLE_v1"
MAX_RUN = 255  # cap por entrada para que cuente quepa en un byte conceptual

StepCallback = Optional[Callable[[str], None]]


def _runs(data: bytes) -> Iterator[tuple[int, int]]:
    """Itera sobre (byte, cuenta) con cuenta limitada a MAX_RUN."""
    if not data:
        return
    current = data[0]
    count = 1
    for b in data[1:]:
        if b == current and count < MAX_RUN:
            count += 1
        else:
            yield current, count
            current = b
            count = 1
    yield current, count


def encode(data: bytes,
           log: StepCallback = None,
           on_tree: Optional[Callable] = None) -> str:
    """Codifica `data` como RLE.

    `on_tree` se acepta por simetria con los otros algoritmos, pero RLE no
    construye arbol; siempre se invoca con (None, None, freqs_de_bytes) para
    que la GUI pueda seguir mostrando frecuencias en el panel de analisis.
    """
    if log:
        log(f"== {ALGORITHM_NAME}: CODIFICACION ==")
        log(f"Paso 1: Leer entrada ({len(data)} bytes)")
    if not data:
        raise ValueError("No hay datos para codificar.")

    if log:
        log(f"Paso 2: Detectar runs (secuencias consecutivas del mismo byte, "
            f"max {MAX_RUN})")
    runs = list(_runs(data))
    if log:
        log(f"  Runs detectados: {len(runs)}")
        if runs:
            longest = max(runs, key=lambda r: r[1])
            shortest = min(runs, key=lambda r: r[1])
            avg_run = sum(c for _, c in runs) / len(runs)
            log(f"  Run mas largo: byte {longest[0]} (0x{longest[0]:02X}) "
                f"x {longest[1]}")
            log(f"  Run mas corto: byte {shortest[0]} (0x{shortest[0]:02X}) "
                f"x {shortest[1]}")
            log(f"  Longitud media de run: {avg_run:.2f} bytes")

    if log:
        log("Paso 3: Serializar cada run como token 'NN*HH' (cuenta decimal "
            "* byte en hex)")
    tokens = [f"{cnt}*{byte:02X}" for byte, cnt in runs]
    body = " ".join(tokens)
    if log and tokens:
        preview = " ".join(tokens[:8]) + (" ..." if len(tokens) > 8 else "")
        log(f"  Primeros tokens: {preview}")

    if log:
        log("Paso 4: Serializar cabecera + tokens")
    header = {
        "algorithm": ALGORITHM_NAME,
        "version": 1,
        "original_size": len(data),
        "run_count": len(runs),
    }
    text = (
        FORMAT_HEADER + "\n"
        + json.dumps(header, separators=(",", ":")) + "\n"
        + body
    )

    # Frecuencias por byte para que la GUI pueda mostrarlas en analisis.
    if on_tree:
        freqs: dict = {}
        for byte, cnt in runs:
            freqs[byte] = freqs.get(byte, 0) + cnt
        on_tree(None, None, freqs)

    if log:
        ratio = len(text) / len(data) * 100 if data else 0
        log(f"  Tamano original: {len(data)} bytes")
        log(f"  Tokens emitidos: {len(tokens)}")
        log(f"  Tamano del .txt resultante: {len(text)} caracteres "
            f"({ratio:.1f}% del original)")
        if ratio > 100:
            log("  AVISO: la salida es mayor que la entrada. RLE expande "
                "datos sin runs largos.")
        log("Codificacion completada.")
    return text


def decode(text: str,
           log: StepCallback = None,
           on_tree: Optional[Callable] = None) -> bytes:
    if log:
        log(f"== {ALGORITHM_NAME}: DECODIFICACION ==")
        log("Paso 1: Validar cabecera y parsear JSON")
    text = text.strip()
    parts = text.split("\n", 2)
    if len(parts) != 3 or parts[0].strip() != FORMAT_HEADER:
        raise ValueError(f"Formato no reconocido. Se esperaba cabecera '{FORMAT_HEADER}'.")
    payload = json.loads(parts[1])
    body = parts[2]

    if log:
        run_count = payload.get("run_count", "desconocido")
        log(f"  Runs declarados en cabecera: {run_count}")

    if log:
        log("Paso 2: Decodificar tokens 'NN*HH' y emitir bytes")
    out = bytearray()
    freqs: dict = {}
    for tok in body.split():
        if "*" not in tok:
            raise ValueError(f"Token invalido (sin separador '*'): '{tok}'")
        cnt_s, byte_s = tok.split("*", 1)
        try:
            cnt = int(cnt_s)
            byte = int(byte_s, 16)
        except ValueError as exc:
            raise ValueError(f"Token invalido: '{tok}'") from exc
        if not (1 <= cnt <= MAX_RUN):
            raise ValueError(f"Cuenta de run fuera de rango (1..{MAX_RUN}): {cnt}")
        if not (0 <= byte <= 255):
            raise ValueError(f"Byte fuera de rango (0..255): {byte}")
        out.extend([byte] * cnt)
        freqs[byte] = freqs.get(byte, 0) + cnt

    if on_tree:
        on_tree(None, None, freqs)

    if log:
        expected = payload.get("original_size")
        if expected is not None and expected != len(out):
            log(f"  ADVERTENCIA: se esperaban {expected} bytes pero se obtuvieron {len(out)}")
        else:
            log(f"  Bytes reconstruidos: {len(out)}")
        log("Decodificacion completada.")
    return bytes(out)
