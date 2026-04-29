# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python main.py                         # run the Tkinter app
pytest                                 # run the full suite (verbose by default via pytest.ini)
pytest tests/test_formats.py           # run one file
pytest tests/test_formats.py::TestSniffExtension::test_png_is_detected   # run one test
pyinstaller milloxcoder.spec           # rebuild dist/milloxcoder.exe (Windows binary)
```

The repo ships `.venv/` ignored; on a fresh checkout do `python -m venv .venv && pip install -r requirements.txt`. On Linux, Tkinter must be installed at the system level (`sudo apt install python3-tk`).

## Architecture

Three modules with a clean GUI/algorithm split:

- **`huffman.py`** — pure algorithm, zero GUI deps. `encode(data, log=None, on_tree=None)` and `decode(text, log=None, on_tree=None)` accept optional callbacks so the GUI can stream step-by-step output to its log panel and capture the tree mid-flow. The functions never import Tkinter; this is what lets `tests/test_huffman.py` and `tests/test_formats.py` run headless.
- **`gui.py`** — single `App` class (~3000 lines) plus two reusable canvas widgets (`RoundedButton`, `StepperBar`). Wire format and source-of-truth conventions below.
- **`main.py`** — three-line entry point.

### Wire format (the encoded `.txt`)

```
HUFFMAN_v1\n
{"algorithm":"Huffman Coding","version":2,"frequencies":{...},"original_size":N,"bit_length":M}\n
0101010101...
```

Three lines, exactly. `decode()` does `text.split("\n", 2)` and rejects anything else. The bitstream tolerates whitespace/newlines on read (so editor-wrapped pastes work), but is emitted as a single line.

The README.md still describes a v1 base64 format — that's stale; ignore it. The actual format is v2 with a raw `01` bitstream as the third line.

### GUI source-of-truth invariants

- `self.encoded_text` is the canonical encoded payload. `do_decode` reads from it directly; do **not** read from `self.bits_text` or `self.json_text` widgets — those are display-only and read-only after `_set_output()`.
- `self.loaded_path` and `self.encoded_source_path` are the two file-origin pointers. They drive the smart filename suggestion in `_suggest_decoded_name()`. Keep them in sync: setting one usually clears the other (see `load_media`, `load_encoded`, `_paste_encoded_dialog`, `clear`).
- `FONT_FAMILY` and `MONO_FAMILY` are module-level globals mutated in `main()` after Tk init (Tkinter font enumeration only works post-Tk). Don't capture them at import time in widget classes; reference them at construction.
- `DISPLAY_LIMIT = 60_000` truncates the embedded panels; the expanded modals use a higher `_BITS_MODAL_LIMIT = 200_000`. Always operate on `self.encoded_text` for actual saves/copies, never on widget contents.

### Filename conventions

- Save encoded: `coded-{stem}.txt` (derived from `loaded_path.stem`).
- Save decoded: `restored-{stem}{ext}` via `_suggest_decoded_name()`. Falls back through `loaded_path` → `coded-` prefix recovery → magic-byte sniffer (`_sniff_extension`).

When adding a new flow that produces files, follow these prefixes — tests parametrize on them.

## Design system (non-optional)

`PRODUCT.md` and `DESIGN.md` are the design system; `gui.py` is held to them. Read them before any UI change.

- Spanish copy, **no em dashes** (`—` or `--`) anywhere — not in user-facing strings, not as empty-value placeholders. Use the `EMPTY_VALUE = "·"` (middle dot) constant for empty metric values.
- Restrained palette: warm tinted neutrals + one vermellon accent. Never `#000`/`#fff`. Color tokens are defined as `COL_*` constants near the top of `gui.py` and mirror the `DESIGN.md` table.
- No side-stripe borders, no gradient text, no glassmorphism, no SaaS hero-metric template, no identical card grids. The `_make_metric` helper deliberately ships two sizes (`big=True/False`) to avoid the identical-grid anti-pattern.
- The `impeccable` skill (in `.claude/skills/impeccable`) is the long-form spec for design work; invoking `/impeccable` in this repo loads the full design framework.

## Tests

`tests/conftest.py` provides synthetic byte fixtures for common formats (PNG, WAV); `tests/test_formats.py` extends with JPEG, GIF, MP3, FLAC, MP4, PDF, UTF-8 and tests the `_sniff_extension` / `_suggest_decoded_name` helpers (both `@staticmethod` so tests don't need a Tk display). The `TestRealImageFlow` class in `test_integration.py` skips if `tests/logo-test.jpg` is missing.

For GUI tests that need a `tk.Tk()`, follow `test_pick_font_returns_string`: wrap in `try: root = tk.Tk()` / `except tk.TclError: pytest.skip("No hay display disponible")`.
