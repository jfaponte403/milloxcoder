"""Huffman coding sobre bytes crudos, con log paso a paso del algoritmo."""

from __future__ import annotations

import heapq
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional

ALGORITHM_NAME = "Huffman Coding"
FORMAT_HEADER = "HUFFMAN_v1"

StepCallback = Optional[Callable[[str], None]]


@dataclass(order=True)
class Node:
    freq: int
    order: int = field(compare=True)
    byte: Optional[int] = field(default=None, compare=False)
    left: Optional["Node"] = field(default=None, compare=False)
    right: Optional["Node"] = field(default=None, compare=False)

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


def _build_frequency_table(data: bytes) -> dict:
    return dict(Counter(data))


def _build_tree(freqs: dict, log: StepCallback = None) -> Node:
    heap: list = []
    counter = 0
    for byte, freq in freqs.items():
        heapq.heappush(heap, Node(freq=freq, order=counter, byte=byte))
        counter += 1
    if log:
        log(f"  Cola de prioridad inicial: {len(heap)} hojas")

    merges = 0
    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        parent = Node(
            freq=left.freq + right.freq,
            order=counter,
            left=left,
            right=right,
        )
        counter += 1
        heapq.heappush(heap, parent)
        merges += 1
        if log:
            l_desc = f"byte {left.byte}" if left.is_leaf else f"subarbol(f={left.freq})"
            r_desc = f"byte {right.byte}" if right.is_leaf else f"subarbol(f={right.freq})"
            log(f"  Fusion #{merges}: {l_desc}(f={left.freq}) + {r_desc}(f={right.freq}) -> nodo f={parent.freq}")
    if log:
        log(f"  Fusiones totales: {merges}")
    return heap[0]


def _build_codes(root: Node) -> dict:
    codes: dict = {}
    # Caso borde: un solo simbolo distinto -> codigo de 1 bit
    if root.is_leaf:
        codes[root.byte] = "0"
        return codes

    stack = [(root, "")]
    while stack:
        node, prefix = stack.pop()
        if node.is_leaf:
            codes[node.byte] = prefix
            continue
        if node.left is not None:
            stack.append((node.left, prefix + "0"))
        if node.right is not None:
            stack.append((node.right, prefix + "1"))
    return codes


def encode(data: bytes, log: StepCallback = None, on_tree: Optional[Callable[["Node", dict, dict], None]] = None) -> str:
    if log:
        log(f"== {ALGORITHM_NAME}: CODIFICACION ==")
        log(f"Paso 1: Leer entrada ({len(data)} bytes)")
    if not data:
        raise ValueError("No hay datos para codificar.")

    freqs = _build_frequency_table(data)
    if log:
        log(f"Paso 2: Tabla de frecuencias ({len(freqs)} simbolos distintos)")
        for byte, freq in sorted(freqs.items(), key=lambda x: -x[1]):
            log(f"  byte {byte:>3} (0x{byte:02X}): {freq}")

    if log:
        log("Paso 3: Construir arbol Huffman (fusion repetida de los 2 nodos de menor frecuencia)")
    root = _build_tree(freqs, log=log)

    if log:
        log("Paso 4: Generar codigos binarios recorriendo el arbol (izq=0, der=1)")
    codes = _build_codes(root)
    if on_tree:
        on_tree(root, codes, freqs)
    if log:
        for byte, code in sorted(codes.items(), key=lambda x: (len(x[1]), x[0])):
            log(f"  byte {byte:>3} (0x{byte:02X}) -> {code}")
        avg = sum(len(codes[b]) * f for b, f in freqs.items()) / len(data)
        log(f"  Longitud media de codigo: {avg:.3f} bits/byte (vs 8 bits/byte sin comprimir)")

    if log:
        log("Paso 5: Sustituir cada byte por su codigo y concatenar los bits")
    bits = "".join(codes[b] for b in data)
    if log:
        log(f"  Flujo de bits generado: {len(bits)} bits")
        preview = bits[:64] + ("..." if len(bits) > 64 else "")
        log(f"  Primeros bits: {preview}")

    if log:
        log("Paso 6: Serializar cabecera (frecuencias) + bitstream legible")
    header = {
        "algorithm": ALGORITHM_NAME,
        "version": 2,
        "frequencies": {str(b): f for b, f in freqs.items()},
        "original_size": len(data),
        "bit_length": len(bits),
    }
    text = (
        FORMAT_HEADER + "\n"
        + json.dumps(header, separators=(",", ":")) + "\n"
        + bits
    )
    if log:
        ratio_bits = len(bits) / (len(data) * 8) * 100
        log(f"  Tamano original: {len(data)} bytes ({len(data) * 8} bits)")
        log(f"  Bits codificados: {len(bits)} ({ratio_bits:.1f}% del original)")
        log(f"  Tamano del .txt resultante: {len(text)} caracteres")
        log("Codificacion completada.")
    return text


def decode(text: str, log: StepCallback = None, on_tree: Optional[Callable[["Node", dict, dict], None]] = None) -> bytes:
    if log:
        log(f"== {ALGORITHM_NAME}: DECODIFICACION ==")
        log("Paso 1: Validar cabecera, parsear JSON y leer bitstream")
    text = text.strip()
    parts = text.split("\n", 2)
    if len(parts) != 3 or parts[0].strip() != FORMAT_HEADER:
        raise ValueError(f"Formato no reconocido. Se esperaba cabecera '{FORMAT_HEADER}'.")
    payload = json.loads(parts[1])
    freqs = {int(b): f for b, f in payload["frequencies"].items()}
    bits = "".join(parts[2].split())
    bit_length = int(payload.get("bit_length", len(bits)))
    if bit_length < len(bits):
        bits = bits[:bit_length]
    if any(c not in "01" for c in bits):
        raise ValueError("El bitstream contiene caracteres no binarios.")
    if log:
        log(f"  {len(freqs)} simbolos, {len(bits)} bits de entrada")

    if log:
        log("Paso 2: Reconstruir el arbol Huffman con las mismas frecuencias")
    root = _build_tree(freqs, log=log)
    if on_tree:
        on_tree(root, _build_codes(root), freqs)

    if log:
        log("Paso 3: Recorrer el arbol bit a bit; al llegar a una hoja emitir su byte y volver a la raiz")
    out = bytearray()
    if root.is_leaf:
        # Caso borde de un solo simbolo: cada bit '0' produce ese byte
        out.extend([root.byte] * len(bits))
    else:
        node = root
        for bit in bits:
            node = node.left if bit == "0" else node.right
            if node is None:
                raise ValueError("Flujo de bits invalido: camino truncado en el arbol.")
            if node.is_leaf:
                out.append(node.byte)
                node = root

    if log:
        expected = payload.get("original_size")
        if expected is not None and expected != len(out):
            log(f"  ADVERTENCIA: se esperaban {expected} bytes pero se obtuvieron {len(out)}")
        else:
            log(f"  Bytes reconstruidos: {len(out)}")
        log("Decodificacion completada.")
    return bytes(out)
