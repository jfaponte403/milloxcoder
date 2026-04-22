# Milloxcoder

Aplicacion de escritorio en Python puro (Tkinter) que permite cargar una imagen
o un audio, **codificarlo** y **decodificarlo** con el algoritmo **Huffman
Coding**, mostrando en pantalla el proceso paso a paso.

## Caracteristicas

- GUI con Tkinter (incluido en Python, sin dependencias externas).
- Carga cualquier archivo de imagen o audio (opera sobre los bytes crudos).
- Codifica con Huffman y muestra:
  - Tabla de frecuencias.
  - Construccion del arbol (fusiones).
  - Tabla de codigos resultante.
  - Longitud media de codigo y ratio de compresion.
- Decodifica reconstruyendo el arbol y recorriendolo bit a bit.
- El resultado codificado se puede:
  - Ver en la interfaz.
  - Copiar al portapapeles.
  - Guardar como archivo `.txt` (texto JSON con la cabecera `HUFFMAN_v1`).
- Se puede volver a cargar el `.txt` codificado y reconstruir el archivo
  original, guardandolo de vuelta a disco.

## Requisitos

- Python 3.9 o superior (probado con 3.14).
- En Linux, instalar Tkinter si no esta: `sudo apt install python3-tk`.

## Instalacion y ejecucion

Clona el repositorio y entra al directorio del proyecto:

```bash
git clone <url-del-repo>
cd milloxcoder
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Windows (CMD)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python main.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Dependencias

- `Pillow>=10.0` para exportar el arbol de Huffman a PNG/JPEG.
- `pytest>=8.0` para ejecutar la suite de tests en `tests/`.

### Ejecutar los tests

```bash
pytest
```

## Uso

1. **Cargar imagen/audio**: abre el archivo de origen.
2. **Codificar**: aplica Huffman y muestra el proceso en el panel superior y el
   resultado codificado (texto JSON) en el panel inferior.
3. **Copiar resultado** / **Guardar .txt codificado**: exporta el resultado.
4. **Cargar .txt codificado**: abre un resultado previamente guardado.
5. **Decodificar**: reconstruye los bytes originales.
6. **Guardar media decodificada**: escribe los bytes reconstruidos a disco
   (usa la misma extension del archivo original para reabrirlo).

## Formato del .txt codificado

```
HUFFMAN_v1
{
  "algorithm": "Huffman Coding",
  "version": 1,
  "frequencies": { "0": 12, "1": 5, ... },
  "padding": 4,
  "data": "<bytes empaquetados en base64>",
  "original_size": 1234
}
```

## Archivos

- `main.py` - punto de entrada.
- `gui.py` - interfaz Tkinter.
- `huffman.py` - algoritmo Huffman con callback de pasos.
- `tests/` - suite de tests con pytest.
- `requirements.txt` - dependencias (Pillow, pytest).
- `pytest.ini` - configuracion de pytest.
- `.gitignore` - ignora el entorno virtual (`.venv/`), caches de Python
  (`__pycache__/`, `*.pyc`), cache de pytest (`.pytest_cache/`), carpetas de
  IDEs (`.idea/`, `.vscode/`), directorio de Claude Code (`.claude/`),
  artefactos de empaquetado (`build/`, `dist/`, `*.egg-info/`) y archivos
  generados por el SO (`.DS_Store`, `Thumbs.db`).
