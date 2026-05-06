"""Registro unificado de los algoritmos de codificacion soportados.

La GUI usa este modulo para elegir el codificador segun el selector y para
auto-detectar el algoritmo a la hora de decodificar a partir de la cabecera
del wire format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import huffman
import rle


@dataclass(frozen=True)
class Algorithm:
    key: str
    name: str
    short_name: str
    header: str
    encode: Callable
    decode: Callable
    has_tree: bool
    description: str


ALGORITHMS: dict[str, Algorithm] = {
    "huffman": Algorithm(
        key="huffman",
        name=huffman.ALGORITHM_NAME,
        short_name="Huffman",
        header=huffman.FORMAT_HEADER,
        encode=huffman.encode,
        decode=huffman.decode,
        has_tree=True,
        description=(
            "Codificacion por entropia optima. Construye un arbol binario "
            "fusionando los dos nodos de menor frecuencia hasta que queda uno."
        ),
    ),
    "rle": Algorithm(
        key="rle",
        name=rle.ALGORITHM_NAME,
        short_name="RLE",
        header=rle.FORMAT_HEADER,
        encode=rle.encode,
        decode=rle.decode,
        has_tree=False,
        description=(
            "Codificacion sin entropia, basada en runs. Sustituye secuencias "
            "consecutivas del mismo byte por (cuenta, byte). Brilla en datos "
            "repetitivos; expande datos aleatorios."
        ),
    ),
}

DEFAULT = "huffman"
ORDER = ("huffman", "rle")


def detect_from_header(text: str) -> str | None:
    """Devuelve la clave del algoritmo a partir de la primera linea del wire,
    o None si la cabecera no coincide con ninguno conocido."""
    head = text.split("\n", 1)[0].strip()
    for key, alg in ALGORITHMS.items():
        if head == alg.header:
            return key
    return None


def get(key: str) -> Algorithm:
    if key not in ALGORITHMS:
        raise KeyError(f"Algoritmo desconocido: {key!r}")
    return ALGORITHMS[key]
