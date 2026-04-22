# Milloxcoder — Explicacion tecnica

Aplicacion de escritorio (Tkinter) que **codifica y decodifica imagenes y audio**
usando el algoritmo de **Huffman** sin perdida. Permite ver paso a paso el
proceso, el arbol binario generado, el bitstream resultante y previsualizar
la media reconstruida.

---

## 1. Arquitectura del proyecto

```
milloxcoder/
├── main.py          Punto de entrada (lanza la GUI)
├── gui.py           Interfaz Tkinter + visualizaciones
├── huffman.py       Algoritmo puro (sin dependencias de UI)
├── tests/           Suite de pytest (55 tests)
│   ├── conftest.py          fixtures
│   ├── test_huffman.py      unidad
│   ├── test_integration.py  flujos + caso real con logo-test.jpg
│   └── logo-test.jpg
├── requirements.txt Pillow, pytest
└── pytest.ini       configuracion de tests
```

**Separacion de responsabilidades**:
- `huffman.py` es agnostico de la UI. Solo expone `encode(bytes) -> str` y
  `decode(str) -> bytes` + callbacks opcionales (`log`, `on_tree`) para
  observar el proceso. Por eso se puede testear sin levantar Tkinter.
- `gui.py` consume esos callbacks para renderizar el log, pintar el arbol
  y actualizar metricas en tiempo real.

---

## 2. Algoritmo de Huffman

Huffman es un **algoritmo de compresion sin perdida** que asigna codigos
binarios de longitud **variable** a cada simbolo: los simbolos mas frecuentes
reciben codigos cortos, los raros reciben codigos largos. Es **prefijo-libre**
(ningun codigo es prefijo de otro), lo que permite decodificar sin ambiguedad.

### 2.1. Codificacion (pasos)

La app lo divide en 6 pasos visibles (indicador superior del tab "Proceso"):

#### Paso 1 — Leer entrada

Se lee el archivo binario como `bytes`. Cada byte (0..255) es un "simbolo".

#### Paso 2 — Tabla de frecuencias

Se cuenta cuantas veces aparece cada byte con `collections.Counter`:

```python
freqs = {65: 12, 66: 3, 67: 47, ...}
```

#### Paso 3 — Construir el arbol de Huffman

Se mete cada simbolo como una **hoja** en una cola de prioridad (min-heap)
ordenada por frecuencia. Mientras quede mas de un nodo:

1. Se extraen los **dos nodos de menor frecuencia** (`heappop`).
2. Se crea un nodo padre con `freq = izq.freq + der.freq` y ambos como hijos.
3. Se reinserta el padre en el heap.

Cuando queda un unico nodo, esa es la **raiz del arbol**.

```
       (15)          <- raiz
       /  \
     (6)  (9)        <- nodos internos (suma de frecuencias)
     / \   / \
    A  B  C  D       <- hojas (simbolos reales)
```

**Desempate determinista**: si dos nodos tienen la misma frecuencia, se usa
un contador incremental (`order`) como criterio secundario del heap. Esto
garantiza que codificar dos veces los mismos bytes produzca el mismo arbol
(necesario para que los tests sean reproducibles).

#### Paso 4 — Generar codigos binarios

Se recorre el arbol desde la raiz: bajar a la **izquierda = 0**,
**derecha = 1**. Al llegar a una hoja, la secuencia acumulada es el codigo
de ese byte:

```
A → 00
B → 01
C → 10
D → 11
```

*Caso borde:* si el archivo solo tiene un simbolo distinto, el arbol es una
sola hoja y se asigna el codigo `"0"` (1 bit por repeticion).

#### Paso 5 — Sustituir cada byte por su codigo

Se concatenan los codigos de todos los bytes de la entrada en un unico string
de ceros y unos. Este es el **bitstream**.

```
entrada:    C A C D B C
codigos:    10 00 10 11 01 10
bitstream:  100010110110
```

#### Paso 6 — Serializar

Se construye un texto UTF-8 con tres lineas:

```
HUFFMAN_v1
{"algorithm":"Huffman Coding","version":2,"frequencies":{...},"original_size":N,"bit_length":M}
010110100101...   <- el bitstream completo
```

Este es el contenido del `.txt` que el usuario guarda/copia/pega.

### 2.2. Decodificacion (pasos)

La decodificacion es el proceso inverso (3 pasos):

#### Paso 1 — Parsear cabecera

- Se valida la linea `HUFFMAN_v1`.
- Se parsea el JSON para recuperar `frequencies` y `bit_length`.
- Se lee el bitstream eliminando saltos de linea/espacios (`"".join(parts[2].split())`).
- Se valida que solo contenga `0` y `1`.

#### Paso 2 — Reconstruir el arbol

Se usa **la misma funcion `_build_tree`** con las mismas frecuencias. Como el
heap es determinista (frecuencia + orden de insercion), el arbol generado es
identico al usado al codificar → los codigos coinciden.

> Esto explica por que basta con guardar las **frecuencias** en el header:
> no hace falta serializar el arbol ni los codigos; se reconstruyen.

#### Paso 3 — Recorrer el bitstream

```
nodo = raiz
para cada bit:
    si bit == '0': nodo = nodo.izq
    sino:          nodo = nodo.der
    si nodo es hoja:
        emitir nodo.byte
        nodo = raiz
```

Al terminar, los bytes emitidos son **exactamente los originales**.

---

## 3. Formato del archivo codificado

```
Linea 1 : HUFFMAN_v1
Linea 2 : JSON compacto { algorithm, version, frequencies, original_size, bit_length }
Linea 3+: bitstream en ASCII '0'/'1' (puede contener saltos de linea cuando
          el usuario lo pega manualmente; la decodificacion los ignora)
```

**Decisiones de diseño:**

- *El bitstream NO se empaqueta en base64.* El anterior formato usaba base64
  para compactar los bits en bytes, pero eso ocultaba el resultado real de
  Huffman. La version actual muestra el bitstream literal para que se vea
  el efecto de la compresion (por ejemplo: `686.691` bits vs `86.832 × 8 =
  694.656` bits originales ≈ 98,8 % → se puede ver directamente).
- *Frecuencias en vez de arbol serializado.* Es mas compacto y el arbol es
  reproducible por determinismo del heap.
- *`bit_length` explicito.* Por si el bitstream se pegara con ruido al final.

---

## 4. Interfaz grafica (`gui.py`)

### 4.1. Paleta y tipografia

- Paleta en grises (`#f5f5f5`, `#ececec`, `#3a3a3a`, `#707070`...).
- Fuente global: **Montserrat** → **Roboto** → **Segoe UI** (fallback
  automatico segun disponibilidad).
- Botones custom `RoundedButton` (clase propia sobre `tk.Canvas`) con
  border-radius de 4 px y estados hover/pressed — porque `ttk.Button` no
  soporta esquinas redondeadas.
- Tabs de tamaño fijo (layout redefinido para quitar el focus border del
  tema clam).

### 4.2. Pestaña "Proceso"

- **Indicador de 6 pasos** que se ilumina conforme avanza el algoritmo.
  Se dispara detectando el prefijo `"Paso N"` en los mensajes del log.
- **Tarjetas de metricas**: entrada, simbolos distintos, bits generados,
  tamaño de salida y ratio de compresion.
- **Log coloreado**: pasos en negrita, detalles en gris, exitos en verde,
  advertencias en naranja.

### 4.3. Pestaña "Arbol de Huffman"

- `tk.Canvas` scrollable que dibuja el arbol construido durante la
  (de)codificacion.
- Hojas en circulos oscuros con el valor del byte; nodos internos en gris
  con la frecuencia; aristas etiquetadas `0`/`1`.
- **Centrar**: desplaza el scroll horizontal al centro del arbol.
- **Exportar imagen**: renderiza el arbol con `PIL.ImageDraw` (no con
  `canvas.postscript`, asi no hace falta Ghostscript) y guarda PNG o JPEG.
- Para arboles enormes (>400 nodos) se limita la cantidad dibujada con un
  recorrido BFS y se avisa al usuario.
- Mecanismo: `encode`/`decode` aceptan un callback `on_tree(root, codes,
  freqs)` que la GUI usa para capturar el arbol sin acoplar modulos.

### 4.4. Pestaña "Resultado"

Muestra el texto codificado completo (cabecera + JSON + bitstream). Si
supera `DISPLAY_LIMIT` (60.000 caracteres) se muestra un preview truncado,
pero el texto completo sigue en `self.encoded_text` para copiar/guardar/
decodificar sin perdida.

### 4.5. Pestaña "Previsualizacion"

Abre los bytes con `PIL.Image.open(BytesIO(data))`. Si son una imagen,
la muestra escalada manteniendo proporcion, con info de formato/dimensiones/
tamaño. Si no (p.ej. audio), muestra un mensaje claro. Se actualiza al
cargar archivo y al decodificar, demostrando visualmente que el roundtrip
no pierde datos.

### 4.6. Flujos de usuario soportados

1. **Cargar archivo → Codificar → Guardar archivo codificado** (produce
   `media-codificada.txt`).
2. **Cargar archivo codificado → Decodificar → Restaurar media codificada**
   (guarda los bytes reconstruidos en cualquier ruta).
3. **Copiar** el texto codificado al portapapeles y **pegarlo** en el panel
   "Resultado" para decodificar sin pasar por archivo.

---

## 5. Correctitud y tests

La carpeta `tests/` contiene **55 tests** en pytest:

- **Unidad (`test_huffman.py`)**: tabla de frecuencias, construccion del
  arbol, propiedad prefijo-libre de los codigos, codificacion, decodificacion,
  callbacks (`log`, `on_tree`), errores esperados, compresion real.
- **Integracion (`test_integration.py`)**: flujos de la GUI (cargar →
  codificar → guardar → cargar → decodificar), tolerancia a copy/paste con
  saltos de linea, determinismo, caso real con `tests/logo-test.jpg`
  (verifica que la imagen reconstruida es **byte a byte** igual a la
  original), smoke tests del modulo GUI.

Ejecutar:

```bash
python -m pytest
```

La propiedad central testeada es `decode(encode(data)) == data` para datos
de distinta naturaleza (texto, bytes repetidos, rango completo 0..255,
PNG real, WAV real, imagen JPEG real, datos aleatorios).

---

## 6. Limitaciones y decisiones

- **No empaqueta en binario**: el `.txt` ocupa 1 char por bit (≈8× el
  archivo empaquetado). Es intencional para hacer el resultado del
  algoritmo visible y verificable a ojo. Si se quisiera optimizar,
  `_pack_bits`/`_unpack_bits` (version 1 del formato, antes de v2) puede
  reintroducirse con padding explicito.
- **Archivos muy grandes**: el algoritmo es O(n log k) donde k es la
  cantidad de simbolos distintos. Para bytes, k ≤ 256, asi que es
  lineal en la practica. La limitacion real es la memoria del bitstream
  como string Python (2 bytes por char en CPython). Archivos > ~100 MB
  pueden ser lentos de mostrar en la UI.
- **Un solo simbolo**: manejado como caso borde (1 bit por byte).
- **Arbol enorme en UI**: el renderizado se limita a 400 nodos para que
  siga siendo legible; el arbol real sigue en memoria.
