"""Interfaz Tkinter de Milloxcoder: codificador/decodificador Huffman con
visualizacion paso a paso y dashboard de teoria de la informacion."""

from __future__ import annotations

import io
import json
import math
import shutil
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, scrolledtext, ttk

from huffman import ALGORITHM_NAME, FORMAT_HEADER, Node, decode, encode


# ---------------------------------------------------------------------------
# Tipografia
# ---------------------------------------------------------------------------

def _pick_font() -> str:
    try:
        families = set(tkfont.families())
    except tk.TclError:
        return "Segoe UI"
    for name in ("Segoe UI", "Helvetica", "Arial"):
        if name in families:
            return name
    return "TkDefaultFont"


def _pick_mono() -> str:
    try:
        families = set(tkfont.families())
    except tk.TclError:
        return "Consolas"
    for name in ("Consolas", "JetBrains Mono", "Courier New", "Courier"):
        if name in families:
            return name
    return "TkFixedFont"


FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

MEDIA_EXTENSIONS = (
    ".png .jpg .jpeg .gif .bmp .tiff .webp "
    ".wav .mp3 .ogg .flac .m4a .aac "
    ".mp4 .webm .avi .mov "
    ".pdf .txt"
)
DISPLAY_LIMIT = 60_000

# Glifo neutro para metricas sin valor todavia. Middle dot, no em dash:
# DESIGN.md prohibe em dashes y `--` en copy.
EMPTY_VALUE = "·"


# ---------------------------------------------------------------------------
# Paleta (calida, restrained, un acento vermellon)
# ---------------------------------------------------------------------------

COL_BG = "#FAF7F2"
COL_SURFACE = "#FFFEFB"
COL_RAISED = "#F4F1EA"
COL_BORDER = "#E5DFD3"
COL_BORDER_SUBTLE = "#EFEAE0"

COL_INK = "#1F1B17"
COL_MUTED = "#6B635A"
COL_SUBTLE = "#A29B91"

COL_ACCENT = "#D74F2A"
COL_ACCENT_HOVER = "#BC4220"
COL_ACCENT_ACTIVE = "#9F3717"
COL_ACCENT_SOFT = "#F8E3D8"

COL_OK = "#2E7D32"
COL_WARN = "#B45309"

COL_TREE_LEAF = "#1F1B17"
COL_TREE_INNER = "#B5AB9D"
COL_TREE_EDGE = "#C9C0B2"

COL_CHART_BAR = COL_ACCENT
COL_CHART_TRACK = "#ECE6DA"
COL_CHART_REF = "#1F1B17"


# ---------------------------------------------------------------------------
# RoundedButton
# ---------------------------------------------------------------------------

class RoundedButton(tk.Canvas):
    """Boton plano con esquinas redondeadas dibujado en Canvas."""

    def __init__(self, parent, text: str, command=None, *,
                 bg: str = COL_RAISED, fg: str = COL_INK,
                 hover_bg: str | None = None, active_bg: str | None = None,
                 font=None, padx: int = 16, pady: int = 9, radius: int = 6,
                 parent_bg: str = COL_BG, bold: bool = False,
                 border: str | None = None) -> None:
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0)
        self.command = command
        self.bg = bg
        self.fg = fg
        self.hover_bg = hover_bg or bg
        self.active_bg = active_bg or hover_bg or bg
        self.radius = radius
        self.border = border
        weight = "bold" if bold else "normal"
        self.font = font or (FONT_FAMILY, 9, weight)
        self.text = text

        tmp = self.create_text(0, 0, text=text, font=self.font, anchor="nw")
        bbox = self.bbox(tmp)
        self.delete(tmp)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        self.w = tw + padx * 2
        self.h = th + pady * 2
        self.configure(width=self.w, height=self.h)

        self._current = bg
        self._draw(self.bg)

        self.bind("<Enter>", lambda e: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self.bg))
        self.bind("<ButtonPress-1>", lambda e: self._draw(self.active_bg))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _round_rect(self, color: str, outline: str | None = None) -> None:
        r = self.radius
        w, h = self.w, self.h
        pts = [
            r, 0, w - r, 0, w, 0, w, r,
            w, h - r, w, h, w - r, h,
            r, h, 0, h, 0, h - r,
            0, r, 0, 0, r, 0,
        ]
        self.create_polygon(
            pts, smooth=True, splinesteps=14,
            fill=color, outline=outline or color,
        )

    def _draw(self, color: str) -> None:
        self._current = color
        self.delete("all")
        self._round_rect(color, outline=self.border)
        self.create_text(self.w / 2, self.h / 2, text=self.text,
                         fill=self.fg, font=self.font)

    def _on_release(self, event) -> None:
        self._draw(self.hover_bg)
        if (0 <= event.x <= self.w) and (0 <= event.y <= self.h):
            if self.command:
                self.command()


# ---------------------------------------------------------------------------
# Stepper visual (dots conectados)
# ---------------------------------------------------------------------------

class StepperBar(tk.Canvas):
    """Barra horizontal con dots numerados conectados por una linea."""

    def __init__(self, parent, steps: list[str], parent_bg: str = COL_BG):
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0,
                         height=70)
        self.steps = steps
        self.parent_bg = parent_bg
        self._state = [0] * len(steps)  # 0 pending, 1 active, 2 done
        self.bind("<Configure>", lambda e: self._draw())

    def reset(self) -> None:
        self._state = [0] * len(self.steps)
        self._draw()

    def mark_active(self, idx: int) -> None:
        for i in range(len(self._state)):
            if i < idx:
                self._state[i] = 2
            elif i == idx:
                self._state[i] = 1
            else:
                self._state[i] = 0
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        n = len(self.steps)
        if n == 0 or w < 60:
            return

        margin = 24
        usable = w - 2 * margin
        if n > 1:
            gap = usable / (n - 1)
        else:
            gap = 0
        cy = 22
        r = 11

        # Linea base
        self.create_line(
            margin, cy, w - margin, cy,
            fill=COL_BORDER, width=2,
        )
        # Linea de progreso (hasta el ultimo activo/done)
        last_done = -1
        for i, s in enumerate(self._state):
            if s >= 1:
                last_done = i
        if last_done >= 0 and n > 1:
            x_end = margin + last_done * gap
            self.create_line(
                margin, cy, x_end, cy,
                fill=COL_ACCENT, width=2,
            )

        for i, label in enumerate(self.steps):
            x = margin + i * gap
            state = self._state[i]
            if state == 2:
                fill = COL_INK
                fg = "#FFFFFF"
                outline = COL_INK
            elif state == 1:
                fill = COL_ACCENT
                fg = "#FFFFFF"
                outline = COL_ACCENT
            else:
                fill = COL_SURFACE
                fg = COL_SUBTLE
                outline = COL_BORDER

            self.create_oval(
                x - r, cy - r, x + r, cy + r,
                fill=fill, outline=outline, width=1.5,
            )
            self.create_text(
                x, cy, text=str(i + 1), fill=fg,
                font=(FONT_FAMILY, 9, "bold"),
            )
            label_color = COL_INK if state >= 1 else COL_MUTED
            label_weight = "bold" if state == 1 else "normal"
            self.create_text(
                x, cy + r + 14, text=label,
                fill=label_color,
                font=(FONT_FAMILY, 8, label_weight),
            )


# ---------------------------------------------------------------------------
# Helpers de teoria de la informacion
# ---------------------------------------------------------------------------

def _calculate_metrics(freqs: dict, codes: dict) -> dict | None:
    if not freqs or not codes:
        return None
    total = sum(freqs.values())
    if total == 0:
        return None

    H = 0.0
    for f in freqs.values():
        if f > 0:
            p = f / total
            H -= p * math.log2(p)

    L = sum((freqs[b] / total) * len(codes[b]) for b in freqs)
    sigma2 = sum((freqs[b] / total) * (len(codes[b]) - L) ** 2 for b in freqs)
    R = L - H
    eta = (H / L) if L > 0 else 0.0

    code_lengths = [len(c) for c in codes.values()]
    return {
        "entropy": H,
        "mean_length": L,
        "redundancy": R,
        "efficiency": eta,
        "variance": sigma2,
        "std_dev": math.sqrt(sigma2),
        "total_symbols": total,
        "unique_symbols": len(freqs),
        "min_code_len": min(code_lengths) if code_lengths else 0,
        "max_code_len": max(code_lengths) if code_lengths else 0,
        "code_length_distribution": _length_distribution(codes, freqs),
    }


def _length_distribution(codes: dict, freqs: dict) -> list[tuple[int, int, int]]:
    """Devuelve [(longitud, simbolos_unicos, ocurrencias_totales)]."""
    by_len: dict[int, list[int]] = {}
    for byte, code in codes.items():
        by_len.setdefault(len(code), []).append(byte)
    rows = []
    for length in sorted(by_len):
        bytes_at = by_len[length]
        unique = len(bytes_at)
        total_occ = sum(freqs.get(b, 0) for b in bytes_at)
        rows.append((length, unique, total_occ))
    return rows


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Milloxcoder · Huffman encoder y decoder")
        self.root.configure(bg=COL_BG)
        self.root.minsize(1040, 680)
        self.root.resizable(True, True)
        self._center_window(1360, 880)

        self.loaded_bytes: bytes | None = None
        self.loaded_path: Path | None = None
        self.encoded_source_path: Path | None = None
        self.encoded_text: str | None = None
        self.decoded_bytes: bytes | None = None
        self.current_root: Node | None = None
        self.current_codes: dict | None = None
        self.current_freqs: dict | None = None
        self.current_metrics: dict | None = None
        self.last_action_label: str = "sin operacion"

        # Estado de reproduccion de la pestana 'Vista previa'.
        self._media_temp_dir: Path | None = None
        self._audio_initialized: bool = False
        self._audio_temp_path: Path | None = None
        self._audio_paused: bool = False
        self._video_cap = None
        self._video_after_id: str | None = None
        self._video_temp_path: Path | None = None
        self._video_frame_delay: int = 33
        self._video_playing: bool = False
        self._video_photo = None
        self._pdf_doc = None
        self._pdf_page_idx: int = 0
        self._pdf_total_pages: int = 0
        self._pdf_label_var: tk.StringVar | None = None

        self._configure_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        try:
            import ctypes
            from ctypes import wintypes
            SPI_GETWORKAREA = 0x0030
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                sw = rect.right - rect.left
                sh = rect.bottom - rect.top
                ox, oy = rect.left, rect.top
            else:
                ox = oy = 0
        except Exception:
            ox = oy = 0
        w = min(width, sw)
        h = min(height, sh)
        x = ox + (sw - w) // 2
        y = oy + (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        f = FONT_FAMILY
        style.configure(".", background=COL_BG, foreground=COL_INK, font=(f, 10))
        style.configure("TFrame", background=COL_BG)
        style.configure("Surface.TFrame", background=COL_SURFACE)
        style.configure("Raised.TFrame", background=COL_RAISED)

        style.configure("TLabel", background=COL_BG, foreground=COL_INK, font=(f, 10))
        style.configure("Surface.TLabel", background=COL_SURFACE, foreground=COL_INK,
                        font=(f, 10))
        style.configure("Raised.TLabel", background=COL_RAISED, foreground=COL_INK,
                        font=(f, 10))
        style.configure("Muted.TLabel", background=COL_BG, foreground=COL_MUTED,
                        font=(f, 9))
        style.configure("MutedRaised.TLabel", background=COL_RAISED,
                        foreground=COL_MUTED, font=(f, 9))
        style.configure("MutedSurface.TLabel", background=COL_SURFACE,
                        foreground=COL_MUTED, font=(f, 9))
        style.configure("Display.TLabel", background=COL_BG, foreground=COL_INK,
                        font=(f, 22, "bold"))
        style.configure("Subhead.TLabel", background=COL_BG, foreground=COL_MUTED,
                        font=(f, 10))
        style.configure("Section.TLabel", background=COL_BG, foreground=COL_INK,
                        font=(f, 11, "bold"))
        style.configure("Eyebrow.TLabel", background=COL_BG, foreground=COL_MUTED,
                        font=(f, 8, "bold"))
        style.configure("EyebrowRaised.TLabel", background=COL_RAISED,
                        foreground=COL_MUTED, font=(f, 8, "bold"))
        style.configure("EyebrowSurface.TLabel", background=COL_SURFACE,
                        foreground=COL_MUTED, font=(f, 8, "bold"))
        style.configure("MetricMain.TLabel", background=COL_RAISED, foreground=COL_INK,
                        font=(f, 20, "bold"))
        style.configure("MetricSec.TLabel", background=COL_RAISED, foreground=COL_INK,
                        font=(f, 15, "bold"))
        style.configure("Status.TLabel", background=COL_BG, foreground=COL_MUTED,
                        font=(f, 9))

        # Notebook tabs
        style.layout("TNotebook.Tab", [
            ("Notebook.tab", {"sticky": "nswe", "children": [
                ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                    ("Notebook.label", {"side": "top", "sticky": ""}),
                ]}),
            ]}),
        ])
        style.configure("TNotebook", background=COL_BG, borderwidth=0,
                        tabmargins=(0, 4, 0, 0))
        style.configure("TNotebook.Tab",
                        background=COL_BG, foreground=COL_MUTED,
                        padding=(16, 9), borderwidth=0, font=(f, 10, "bold"))
        style.map(
            "TNotebook.Tab",
            background=[("selected", COL_BG), ("active", COL_BG)],
            foreground=[("selected", COL_ACCENT), ("active", COL_INK)],
            padding=[("selected", (16, 9)), ("!selected", (16, 9))],
            expand=[("selected", [0, 0, 0, 0])],
        )

        # Scrollbars
        style.configure("Vertical.TScrollbar",
                        background=COL_RAISED, troughcolor=COL_BG,
                        borderwidth=0, arrowcolor=COL_MUTED)
        style.configure("Horizontal.TScrollbar",
                        background=COL_RAISED, troughcolor=COL_BG,
                        borderwidth=0, arrowcolor=COL_MUTED)

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="TFrame")
        outer.pack(fill=tk.BOTH, expand=True, padx=28, pady=20)

        self._build_header(outer)
        self._build_actions(outer)
        self._build_filebar(outer)
        self._build_notebook(outer)
        self._build_statusbar(outer)

    def _build_header(self, parent: ttk.Frame) -> None:
        head = ttk.Frame(parent, style="TFrame")
        head.pack(fill=tk.X, pady=(0, 16))

        left = ttk.Frame(head, style="TFrame")
        left.pack(side=tk.LEFT)
        ttk.Label(left, text="MILLOXCODER", style="Display.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Codifica y decodifica imagen y audio con Huffman, viendo el algoritmo paso a paso.",
            style="Subhead.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        right = ttk.Frame(head, style="TFrame")
        right.pack(side=tk.RIGHT)
        # Badge del algoritmo (acento suave)
        badge = tk.Frame(right, bg=COL_ACCENT_SOFT, padx=12, pady=6)
        badge.pack(side=tk.RIGHT)
        tk.Label(
            badge, text=ALGORITHM_NAME.upper(), bg=COL_ACCENT_SOFT,
            fg=COL_ACCENT_ACTIVE, font=(FONT_FAMILY, 9, "bold"),
        ).pack()

    def _build_actions(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="TFrame")
        wrap.pack(fill=tk.X, pady=(0, 14))

        # Fila 1: acciones primarias
        primary_row = ttk.Frame(wrap, style="TFrame")
        primary_row.pack(fill=tk.X)

        ttk.Label(primary_row, text="ACCIONES", style="Eyebrow.TLabel").pack(
            side=tk.LEFT, padx=(0, 14), pady=(8, 0)
        )

        primary = [
            ("Cargar archivo", self.load_media),
            ("Codificar", self.do_encode),
            ("Decodificar", self.do_decode),
        ]
        for label, cmd in primary:
            RoundedButton(
                primary_row, text=label, command=cmd, bold=True,
                bg=COL_ACCENT, fg="#FFFFFF",
                hover_bg=COL_ACCENT_HOVER, active_bg=COL_ACCENT_ACTIVE,
                parent_bg=COL_BG, padx=18, pady=10,
            ).pack(side=tk.LEFT, padx=(0, 8))

        # Fila 2: secundarias, peso menor
        secondary_row = ttk.Frame(wrap, style="TFrame")
        secondary_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(secondary_row, text="ARCHIVO", style="Eyebrow.TLabel").pack(
            side=tk.LEFT, padx=(0, 18), pady=(8, 0)
        )

        secondary = [
            ("Cargar codificado", self.load_encoded),
            ("Guardar codificado", self.save_encoded),
            ("Restaurar media", self.save_decoded),
            ("Copiar resultado", self.copy_output),
        ]
        for label, cmd in secondary:
            RoundedButton(
                secondary_row, text=label, command=cmd,
                bg=COL_RAISED, fg=COL_INK,
                hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
                parent_bg=COL_BG, padx=14, pady=8,
            ).pack(side=tk.LEFT, padx=(0, 6))

        # Limpiar es destructivo: ghost para que no compita con las demas.
        RoundedButton(
            secondary_row, text="Limpiar", command=self.clear,
            bg=COL_BG, fg=COL_MUTED,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT, padx=(0, 6))

    def _build_filebar(self, parent: ttk.Frame) -> None:
        bar = tk.Frame(parent, bg=COL_RAISED, highlightthickness=0)
        bar.pack(fill=tk.X, pady=(0, 14))

        inner = tk.Frame(bar, bg=COL_RAISED)
        inner.pack(fill=tk.X, padx=14, pady=10)

        tk.Label(
            inner, text="ARCHIVO ACTUAL", bg=COL_RAISED,
            fg=COL_MUTED, font=(FONT_FAMILY, 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.info_var = tk.StringVar(value="Sin archivo cargado.")
        tk.Label(
            inner, textvariable=self.info_var, bg=COL_RAISED, fg=COL_INK,
            font=(FONT_FAMILY, 10),
        ).pack(side=tk.LEFT)

    def _build_notebook(self, parent: ttk.Frame) -> None:
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True)
        self.nb = nb

        self._build_process_tab(nb)
        self._build_analysis_tab(nb)
        self._build_tree_tab(nb)
        self._build_output_tab(nb)
        self._build_preview_tab(nb)

    def _build_statusbar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill=tk.X, pady=(12, 0))

        # Linea horizontal sutil
        rule = tk.Frame(bar, bg=COL_BORDER_SUBTLE, height=1)
        rule.pack(fill=tk.X, pady=(0, 8))

        line = ttk.Frame(bar, style="TFrame")
        line.pack(fill=tk.X)

        self._status_dot = tk.Canvas(line, width=10, height=10, bg=COL_BG,
                                     highlightthickness=0)
        self._status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self._draw_status_dot(COL_OK)

        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(line, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT
        )

    def _draw_status_dot(self, color: str) -> None:
        self._status_dot.delete("all")
        self._status_dot.create_oval(1, 1, 9, 9, fill=color, outline=color)

    # ------------------------------------------------------------------
    # Tab: proceso
    # ------------------------------------------------------------------

    def _build_process_tab(self, nb: ttk.Notebook) -> None:
        frame = tk.Frame(nb, bg=COL_BG)
        nb.add(frame, text=" Proceso ")

        inner = tk.Frame(frame, bg=COL_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        # Stepper
        ttk.Label(inner, text="FASES DEL ALGORITMO", style="Eyebrow.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        self.stepper = StepperBar(
            inner,
            steps=["Leer", "Frecuencias", "Arbol", "Codigos", "Bits", "Serializar"],
            parent_bg=COL_BG,
        )
        self.stepper.pack(fill=tk.X, pady=(0, 18))

        # Metricas en jerarquia 2 + 3
        metrics_label = ttk.Label(inner, text="METRICAS DEL CODIFICADO",
                                  style="Eyebrow.TLabel")
        metrics_label.pack(anchor="w", pady=(0, 6))

        metrics_row = tk.Frame(inner, bg=COL_BG)
        metrics_row.pack(fill=tk.X, pady=(0, 18))

        self.metric_vars = {
            "input": tk.StringVar(value=EMPTY_VALUE),
            "output": tk.StringVar(value=EMPTY_VALUE),
            "symbols": tk.StringVar(value=EMPTY_VALUE),
            "bits": tk.StringVar(value=EMPTY_VALUE),
            "ratio": tk.StringVar(value=EMPTY_VALUE),
        }

        # Dos prominentes
        prominent_row = tk.Frame(metrics_row, bg=COL_BG)
        prominent_row.pack(fill=tk.X)
        self._make_metric(prominent_row, "ENTRADA", "input",
                          big=True, side=tk.LEFT, expand=True)
        self._make_metric(prominent_row, "SALIDA", "output",
                          big=True, side=tk.LEFT, expand=True)

        # Tres secundarios
        sec_row = tk.Frame(metrics_row, bg=COL_BG)
        sec_row.pack(fill=tk.X, pady=(8, 0))
        self._make_metric(sec_row, "SIMBOLOS UNICOS", "symbols",
                          big=False, side=tk.LEFT, expand=True)
        self._make_metric(sec_row, "BITS GENERADOS", "bits",
                          big=False, side=tk.LEFT, expand=True)
        self._make_metric(sec_row, "RATIO BITS/ORIGINAL", "ratio",
                          big=False, side=tk.LEFT, expand=True)

        # Log
        log_label = ttk.Label(inner, text="REGISTRO PASO A PASO",
                              style="Eyebrow.TLabel")
        log_label.pack(anchor="w", pady=(0, 6))

        log_wrap = tk.Frame(inner, bg=COL_BORDER, highlightthickness=0)
        log_wrap.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_wrap, wrap=tk.WORD, font=(MONO_FAMILY, 9),
            bg=COL_SURFACE, fg=COL_INK, insertbackground=COL_INK,
            relief="flat", borderwidth=0, padx=14, pady=12,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.log_text.tag_configure(
            "step", foreground=COL_INK,
            font=(MONO_FAMILY, 10, "bold"), spacing1=8, spacing3=4,
        )
        self.log_text.tag_configure("sub", foreground=COL_MUTED)
        self.log_text.tag_configure(
            "ok", foreground=COL_OK,
            font=(MONO_FAMILY, 9, "bold"),
        )
        self.log_text.tag_configure(
            "warn", foreground=COL_WARN,
            font=(MONO_FAMILY, 9, "bold"),
        )

    def _make_metric(self, parent: tk.Frame, label: str, var_key: str, *,
                     big: bool, side, expand: bool = True) -> None:
        card = tk.Frame(parent, bg=COL_RAISED)
        pad_x = 6 if expand else 0
        card.pack(side=side, fill=tk.X, expand=expand, padx=(0, pad_x))

        inner = tk.Frame(card, bg=COL_RAISED)
        pad_in = (20, 16) if big else (16, 12)
        inner.pack(fill=tk.X, padx=pad_in[0], pady=pad_in[1])

        tk.Label(
            inner, text=label, bg=COL_RAISED, fg=COL_MUTED,
            font=(FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            inner, textvariable=self.metric_vars[var_key], bg=COL_RAISED,
            fg=COL_INK,
            font=(FONT_FAMILY, 20 if big else 14, "bold"),
        ).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # Tab: analisis (dashboard de teoria de la informacion)
    # ------------------------------------------------------------------

    def _build_analysis_tab(self, nb: ttk.Notebook) -> None:
        frame = tk.Frame(nb, bg=COL_BG)
        nb.add(frame, text=" Analisis ")

        # Scrollable
        canvas = tk.Canvas(frame, bg=COL_BG, highlightthickness=0)
        vbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        scroll_frame = tk.Frame(canvas, bg=COL_BG)
        scroll_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(scroll_window, width=event.width)

        scroll_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")

        body = tk.Frame(scroll_frame, bg=COL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        # Sub-header del dashboard
        head = tk.Frame(body, bg=COL_BG)
        head.pack(fill=tk.X)
        ttk.Label(head, text="TEORIA DE LA INFORMACION",
                  style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(
            head,
            text="Metricas calculadas a partir de las frecuencias y los codigos generados.",
            style="Subhead.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        # Empty state
        self.analysis_empty = tk.Frame(body, bg=COL_BG)
        self.analysis_empty.pack(fill=tk.BOTH, expand=True)
        empty_inner = tk.Frame(self.analysis_empty, bg=COL_BG)
        empty_inner.pack(expand=True, pady=80)
        tk.Label(
            empty_inner, text="Aun no hay datos.",
            bg=COL_BG, fg=COL_INK, font=(FONT_FAMILY, 14, "bold"),
        ).pack()
        tk.Label(
            empty_inner,
            text="Codifica o decodifica un archivo para calcular entropia,\n"
                 "longitud media de codigo, redundancia, eficiencia y varianza.",
            bg=COL_BG, fg=COL_MUTED, font=(FONT_FAMILY, 10),
            justify=tk.CENTER,
        ).pack(pady=(8, 0))

        # Contenido (oculto hasta que haya metricas)
        self.analysis_content = tk.Frame(body, bg=COL_BG)

        self._build_analysis_content(self.analysis_content)

    def _build_analysis_content(self, parent: tk.Frame) -> None:
        # Contexto del calculo
        ctx = tk.Frame(parent, bg=COL_RAISED)
        ctx.pack(fill=tk.X)
        ctx_inner = tk.Frame(ctx, bg=COL_RAISED)
        ctx_inner.pack(fill=tk.X, padx=18, pady=12)
        tk.Label(
            ctx_inner, text="FUENTE ANALIZADA", bg=COL_RAISED,
            fg=COL_MUTED, font=(FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")
        self.analysis_source_var = tk.StringVar(value=EMPTY_VALUE)
        tk.Label(
            ctx_inner, textvariable=self.analysis_source_var,
            bg=COL_RAISED, fg=COL_INK, font=(FONT_FAMILY, 11, "bold"),
        ).pack(anchor="w", pady=(2, 0))

        # Tres metricas principales
        ttk.Label(parent, text="VALORES PRINCIPALES",
                  style="Eyebrow.TLabel").pack(anchor="w", pady=(20, 6))

        main_row = tk.Frame(parent, bg=COL_BG)
        main_row.pack(fill=tk.X)

        self.analysis_vars = {
            "H": tk.StringVar(value=EMPTY_VALUE),
            "L": tk.StringVar(value=EMPTY_VALUE),
            "R": tk.StringVar(value=EMPTY_VALUE),
            "eta": tk.StringVar(value=EMPTY_VALUE),
            "sigma2": tk.StringVar(value=EMPTY_VALUE),
            "sigma": tk.StringVar(value=EMPTY_VALUE),
            "min_len": tk.StringVar(value=EMPTY_VALUE),
            "max_len": tk.StringVar(value=EMPTY_VALUE),
        }

        self._make_analysis_card(
            main_row, eyebrow="ENTROPIA",
            symbol="H", var_key="H",
            unit="bits / simbolo",
            description=(
                "Minimo teorico de bits por simbolo segun Shannon. "
                "H = sumatoria de p(x) por log2(1/p(x))."
            ),
            big=True, side=tk.LEFT,
            on_click=lambda: self._show_calc_modal("H"),
        )
        self._make_analysis_card(
            main_row, eyebrow="LONGITUD MEDIA",
            symbol="L", var_key="L",
            unit="bits / simbolo",
            description=(
                "Promedio de bits que Huffman asigna por simbolo. "
                "L = sumatoria de p(x) por longitud(codigo(x))."
            ),
            big=True, side=tk.LEFT,
            on_click=lambda: self._show_calc_modal("L"),
        )
        self._make_analysis_card(
            main_row, eyebrow="REDUNDANCIA",
            symbol="R", var_key="R",
            unit="bits / simbolo",
            description=(
                "Diferencia con el optimo teorico. R = L menos H. "
                "Cuanto mas pequena, mas cerca esta Huffman de Shannon."
            ),
            big=True, side=tk.LEFT,
            on_click=lambda: self._show_calc_modal("R"),
        )

        # Comparacion visual H vs L
        ttk.Label(parent, text="COMPARACION VISUAL",
                  style="Eyebrow.TLabel").pack(anchor="w", pady=(28, 6))

        cmp_box = tk.Frame(parent, bg=COL_SURFACE,
                           highlightthickness=1, highlightbackground=COL_BORDER)
        cmp_box.pack(fill=tk.X)
        cmp_inner = tk.Frame(cmp_box, bg=COL_SURFACE)
        cmp_inner.pack(fill=tk.X, padx=20, pady=18)
        tk.Label(
            cmp_inner, text="Bits por simbolo",
            bg=COL_SURFACE, fg=COL_INK, font=(FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        self.compare_canvas = tk.Canvas(
            cmp_inner, bg=COL_SURFACE, highlightthickness=0, height=130,
        )
        self.compare_canvas.pack(fill=tk.X)
        self.compare_canvas.bind("<Configure>", lambda e: self._draw_compare())

        # Eficiencia y dispersion
        ttk.Label(parent, text="EFICIENCIA Y DISPERSION",
                  style="Eyebrow.TLabel").pack(anchor="w", pady=(28, 6))

        eff_row = tk.Frame(parent, bg=COL_BG)
        eff_row.pack(fill=tk.X)

        self._make_analysis_card(
            eff_row, eyebrow="EFICIENCIA",
            symbol="η", var_key="eta",
            unit="H / L",
            description=(
                "Que tan cerca esta el codigo del optimo teorico. "
                "100 por ciento significa Huffman = Shannon."
            ),
            big=False, side=tk.LEFT,
            on_click=lambda: self._show_calc_modal("eta"),
        )
        self._make_analysis_card(
            eff_row, eyebrow="VARIANZA DE LONGITUD",
            symbol="σ²", var_key="sigma2",
            unit="bits cuadrados",
            description=(
                "Dispersion de las longitudes de codigo respecto a L. "
                "Indica si los codigos son uniformes o muy desiguales."
            ),
            big=False, side=tk.LEFT,
            on_click=lambda: self._show_calc_modal("sigma2"),
        )
        self._make_analysis_card(
            eff_row, eyebrow="DESVIACION ESTANDAR",
            symbol="σ", var_key="sigma",
            unit="bits",
            description=(
                "Raiz cuadrada de la varianza. Misma idea, en bits, "
                "comparable directamente con L."
            ),
            big=False, side=tk.LEFT,
            on_click=lambda: self._show_calc_modal("sigma"),
        )

        # Distribucion de longitudes de codigo
        ttk.Label(parent, text="DISTRIBUCION DE LONGITUDES",
                  style="Eyebrow.TLabel").pack(anchor="w", pady=(28, 6))

        dist_box = tk.Frame(parent, bg=COL_SURFACE,
                            highlightthickness=1, highlightbackground=COL_BORDER)
        dist_box.pack(fill=tk.X)
        dist_inner = tk.Frame(dist_box, bg=COL_SURFACE)
        dist_inner.pack(fill=tk.X, padx=20, pady=18)
        tk.Label(
            dist_inner,
            text="Cuantos simbolos unicos reciben codigos de cada longitud (en bits).",
            bg=COL_SURFACE, fg=COL_MUTED, font=(FONT_FAMILY, 9),
        ).pack(anchor="w", pady=(0, 12))

        self.dist_canvas = tk.Canvas(
            dist_inner, bg=COL_SURFACE, highlightthickness=0, height=180,
        )
        self.dist_canvas.pack(fill=tk.X)
        self.dist_canvas.bind("<Configure>", lambda e: self._draw_distribution())

        # Mini stats al final
        ttk.Label(parent, text="EXTREMOS DE CODIGO",
                  style="Eyebrow.TLabel").pack(anchor="w", pady=(28, 6))

        ext_row = tk.Frame(parent, bg=COL_BG)
        ext_row.pack(fill=tk.X, pady=(0, 24))

        self._make_simple_stat(
            ext_row, "CODIGO MAS CORTO", "min_len", "bits",
            on_click=lambda: self._show_calc_modal("min_len"),
        )
        self._make_simple_stat(
            ext_row, "CODIGO MAS LARGO", "max_len", "bits",
            on_click=lambda: self._show_calc_modal("max_len"),
        )

    def _make_analysis_card(self, parent: tk.Frame, *, eyebrow: str,
                            symbol: str, var_key: str, unit: str,
                            description: str, big: bool, side,
                            on_click=None) -> None:
        card = tk.Frame(parent, bg=COL_SURFACE,
                        highlightthickness=1, highlightbackground=COL_BORDER)
        card.pack(side=side, fill=tk.BOTH, expand=True, padx=(0, 8))
        inner = tk.Frame(card, bg=COL_SURFACE)
        pad = (20, 18) if big else (18, 14)
        inner.pack(fill=tk.BOTH, expand=True, padx=pad[0], pady=pad[1])

        head_row = tk.Frame(inner, bg=COL_SURFACE)
        head_row.pack(fill=tk.X)
        tk.Label(
            head_row, text=eyebrow, bg=COL_SURFACE,
            fg=COL_MUTED, font=(FONT_FAMILY, 8, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            head_row, text=symbol, bg=COL_SURFACE,
            fg=COL_ACCENT, font=(FONT_FAMILY, 12, "bold"),
        ).pack(side=tk.RIGHT)

        size = 26 if big else 20
        tk.Label(
            inner, textvariable=self.analysis_vars[var_key],
            bg=COL_SURFACE, fg=COL_INK,
            font=(FONT_FAMILY, size, "bold"),
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            inner, text=unit, bg=COL_SURFACE,
            fg=COL_SUBTLE, font=(FONT_FAMILY, 9),
        ).pack(anchor="w")

        if big:
            tk.Frame(inner, bg=COL_BORDER_SUBTLE, height=1).pack(
                fill=tk.X, pady=(12, 12)
            )
            tk.Label(
                inner, text=description, bg=COL_SURFACE,
                fg=COL_MUTED, font=(FONT_FAMILY, 9),
                justify=tk.LEFT, wraplength=260,
            ).pack(anchor="w")
        else:
            tk.Label(
                inner, text=description, bg=COL_SURFACE,
                fg=COL_MUTED, font=(FONT_FAMILY, 9),
                justify=tk.LEFT, wraplength=240,
            ).pack(anchor="w", pady=(10, 0))

        if on_click is not None:
            tk.Label(
                inner, text="VER CALCULO  →", bg=COL_SURFACE,
                fg=COL_ACCENT, font=(FONT_FAMILY, 8, "bold"),
            ).pack(anchor="w", pady=(12, 0))
            self._make_clickable(card, on_click)

    def _make_simple_stat(self, parent: tk.Frame, label: str,
                          var_key: str, unit: str,
                          on_click=None) -> None:
        card = tk.Frame(parent, bg=COL_RAISED,
                        highlightthickness=1,
                        highlightbackground=COL_RAISED)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        inner = tk.Frame(card, bg=COL_RAISED)
        inner.pack(fill=tk.X, padx=18, pady=14)
        tk.Label(
            inner, text=label, bg=COL_RAISED, fg=COL_MUTED,
            font=(FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")
        row = tk.Frame(inner, bg=COL_RAISED)
        row.pack(anchor="w", pady=(4, 0))
        tk.Label(
            row, textvariable=self.analysis_vars[var_key],
            bg=COL_RAISED, fg=COL_INK, font=(FONT_FAMILY, 18, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            row, text=" " + unit, bg=COL_RAISED, fg=COL_SUBTLE,
            font=(FONT_FAMILY, 10),
        ).pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))

        if on_click is not None:
            tk.Label(
                inner, text="VER CALCULO  →", bg=COL_RAISED,
                fg=COL_ACCENT, font=(FONT_FAMILY, 8, "bold"),
            ).pack(anchor="w", pady=(8, 0))
            self._make_clickable(card, on_click,
                                 normal=COL_RAISED, hover=COL_ACCENT)

    def _make_clickable(self, card: tk.Frame, on_click,
                        normal: str = COL_BORDER,
                        hover: str = COL_ACCENT) -> None:
        """Hace todo el card clickeable, con cursor pointer y hover de borde."""
        state = {"depth": 0}

        def refresh() -> None:
            card.configure(highlightbackground=hover if state["depth"] > 0 else normal)

        def on_enter(_e=None) -> None:
            state["depth"] += 1
            refresh()

        def on_leave(_e=None) -> None:
            state["depth"] = max(0, state["depth"] - 1)
            refresh()

        def bind_recursive(widget) -> None:
            try:
                widget.configure(cursor="hand2")
            except tk.TclError:
                pass
            widget.bind("<Button-1>", lambda e: on_click(), add="+")
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            for child in widget.winfo_children():
                bind_recursive(child)

        bind_recursive(card)

    def _draw_compare(self) -> None:
        c = self.compare_canvas
        c.delete("all")
        m = self.current_metrics
        if not m:
            return
        H = m["entropy"]
        L = m["mean_length"]
        if max(H, L) <= 0:
            return

        c.update_idletasks()
        w = max(c.winfo_width(), 1)
        h = max(c.winfo_height(), 1)
        if w < 100:
            return

        label_x = 30
        track_x0 = 90
        track_x1 = w - 110
        if track_x1 <= track_x0 + 60:
            track_x1 = track_x0 + 60
        track_w = track_x1 - track_x0

        scale = max(H, L)
        bar_h = 22
        gap = 36
        y0 = 18

        def draw_row(label: str, value: float, color: str, y: int,
                     formatted: str) -> None:
            c.create_text(
                label_x, y + bar_h / 2, text=label, anchor="w",
                fill=COL_INK, font=(FONT_FAMILY, 10, "bold"),
            )
            # track
            c.create_rectangle(
                track_x0, y, track_x1, y + bar_h,
                fill=COL_CHART_TRACK, outline="",
            )
            # bar
            bar_w = int(track_w * (value / scale))
            c.create_rectangle(
                track_x0, y, track_x0 + bar_w, y + bar_h,
                fill=color, outline="",
            )
            c.create_text(
                track_x1 + 12, y + bar_h / 2, text=formatted, anchor="w",
                fill=COL_INK, font=(FONT_FAMILY, 10, "bold"),
            )

        draw_row("H", H, COL_INK, y0, f"{H:.4f}")
        draw_row("L", L, COL_ACCENT, y0 + gap, f"{L:.4f}")

        # Linea de redundancia
        if L > H:
            c.create_text(
                track_x0, y0 + gap * 2 + 6,
                text=f"Brecha (R = L − H) ≈ {L - H:.4f} bits/simbolo",
                anchor="w", fill=COL_MUTED, font=(FONT_FAMILY, 9, "italic"),
            )

    def _draw_distribution(self) -> None:
        c = self.dist_canvas
        c.delete("all")
        m = self.current_metrics
        if not m or not m.get("code_length_distribution"):
            return
        rows = m["code_length_distribution"]
        c.update_idletasks()
        w = max(c.winfo_width(), 1)
        h = max(c.winfo_height(), 1)
        if w < 100 or h < 80:
            return

        margin_x = 36
        margin_y = 22
        plot_w = w - 2 * margin_x
        plot_h = h - 2 * margin_y - 14  # espacio para etiquetas inferiores
        n = len(rows)
        if n == 0 or plot_w < 20:
            return

        gap = 8
        bar_w = max(12, (plot_w - gap * (n - 1)) // n)
        max_unique = max(r[1] for r in rows)
        if max_unique <= 0:
            return

        for i, (length, unique, total) in enumerate(rows):
            x0 = margin_x + i * (bar_w + gap)
            x1 = x0 + bar_w
            bar_h = int((unique / max_unique) * plot_h)
            y1 = h - margin_y - 14
            y0 = y1 - bar_h

            # track sutil
            c.create_rectangle(
                x0, h - margin_y - 14 - plot_h, x1, y1,
                fill=COL_CHART_TRACK, outline="",
            )
            # bar
            c.create_rectangle(
                x0, y0, x1, y1, fill=COL_ACCENT, outline="",
            )
            # valor encima
            c.create_text(
                (x0 + x1) / 2, y0 - 8,
                text=str(unique), fill=COL_INK,
                font=(FONT_FAMILY, 9, "bold"),
            )
            # etiqueta inferior
            c.create_text(
                (x0 + x1) / 2, y1 + 12,
                text=f"{length} bit",
                fill=COL_MUTED, font=(FONT_FAMILY, 8),
            )

    # ------------------------------------------------------------------
    # Tab: arbol
    # ------------------------------------------------------------------

    def _build_tree_tab(self, nb: ttk.Notebook) -> None:
        frame = tk.Frame(nb, bg=COL_BG)
        nb.add(frame, text=" Arbol ")

        inner = tk.Frame(frame, bg=COL_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        top = tk.Frame(inner, bg=COL_BG)
        top.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            top, text="ARBOL DE HUFFMAN", style="Eyebrow.TLabel",
        ).pack(side=tk.LEFT, pady=(8, 0))

        controls = tk.Frame(top, bg=COL_BG)
        controls.pack(side=tk.RIGHT)

        RoundedButton(
            controls, text="Exportar imagen", command=self._export_tree,
            bg=COL_RAISED, fg=COL_INK, hover_bg=COL_BORDER_SUBTLE,
            active_bg=COL_BORDER, parent_bg=COL_BG,
        ).pack(side=tk.RIGHT, padx=(6, 0))
        RoundedButton(
            controls, text="Centrar", command=self._center_tree,
            bg=COL_RAISED, fg=COL_INK, hover_bg=COL_BORDER_SUBTLE,
            active_bg=COL_BORDER, parent_bg=COL_BG,
        ).pack(side=tk.RIGHT, padx=(6, 0))
        RoundedButton(
            controls, text="Ajustar", command=self._redraw_tree,
            bg=COL_RAISED, fg=COL_INK, hover_bg=COL_BORDER_SUBTLE,
            active_bg=COL_BORDER, parent_bg=COL_BG,
        ).pack(side=tk.RIGHT, padx=(6, 0))

        # Leyenda
        legend = tk.Frame(top, bg=COL_BG)
        legend.pack(side=tk.RIGHT, padx=18, pady=(8, 0))
        for col, txt in [(COL_TREE_LEAF, "hoja (byte)"),
                         (COL_TREE_INNER, "interno")]:
            sw = tk.Frame(legend, bg=col, width=10, height=10)
            sw.pack(side=tk.LEFT, padx=(8, 4))
            tk.Label(legend, text=txt, bg=COL_BG, fg=COL_MUTED,
                     font=(FONT_FAMILY, 8)).pack(side=tk.LEFT)

        wrap = tk.Frame(inner, bg=COL_BORDER, highlightthickness=0)
        wrap.pack(fill=tk.BOTH, expand=True)

        self.tree_canvas = tk.Canvas(wrap, bg=COL_SURFACE, highlightthickness=0)
        hbar = ttk.Scrollbar(wrap, orient="horizontal",
                             command=self.tree_canvas.xview)
        vbar = ttk.Scrollbar(wrap, orient="vertical",
                             command=self.tree_canvas.yview)
        self.tree_canvas.configure(xscrollcommand=hbar.set,
                                   yscrollcommand=vbar.set)
        self.tree_canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self.tree_canvas.bind("<Configure>", lambda e: self._redraw_tree())
        self._draw_tree_placeholder()

    # ------------------------------------------------------------------
    # Tab: resultado
    # ------------------------------------------------------------------

    def _build_output_tab(self, nb: ttk.Notebook) -> None:
        frame = tk.Frame(nb, bg=COL_BG)
        nb.add(frame, text=" Resultado ")

        inner = tk.Frame(frame, bg=COL_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        # Grid: header, chips, eficacia, eyebrow bits, panel bits (peso 2),
        #       eyebrow json, panel json (peso 1).
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(4, weight=2, minsize=180)
        inner.rowconfigure(6, weight=1, minsize=120)

        # StringVars del strip de eficacia.
        self.output_compression_var = tk.StringVar(value=EMPTY_VALUE)
        self.output_savings_var = tk.StringVar(value=EMPTY_VALUE)
        self.output_verify_var = tk.StringVar(value=EMPTY_VALUE)
        self.output_verify_sub_var = tk.StringVar(value="tras decodificar")

        # --- Header zone ---
        head = tk.Frame(inner, bg=COL_BG)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        head_text = tk.Frame(head, bg=COL_BG)
        head_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(
            head_text, text="TEXTO CODIFICADO", style="Eyebrow.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            head_text,
            text="Cabecera, secuencia de bits y metadatos JSON, "
                 "cada uno en su propio panel.",
            style="Subhead.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        head_actions = tk.Frame(head, bg=COL_BG)
        head_actions.pack(side=tk.RIGHT, pady=(8, 0))
        RoundedButton(
            head_actions, text="Pegar texto crudo...",
            command=self._paste_encoded_dialog,
            bg=COL_BG, fg=COL_MUTED,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=12, pady=7,
        ).pack()

        # --- Chips zone ---
        self.output_chip_row = tk.Frame(inner, bg=COL_BG)
        self.output_chip_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        # --- Eficacia strip (tasa, ahorro, verificacion) ---
        eff_box = tk.Frame(inner, bg=COL_RAISED)
        eff_box.grid(row=2, column=0, sticky="ew", pady=(0, 22))
        eff_grid = tk.Frame(eff_box, bg=COL_RAISED)
        eff_grid.pack(fill=tk.X)
        for col in (0, 2, 4):
            eff_grid.columnconfigure(col, weight=1, uniform="eff")

        self._build_eff_cell(
            eff_grid, 0, "TASA DE COMPRESION",
            sub_text="del tamano original",
            value_var=self.output_compression_var,
            on_click=lambda: self._show_efficacy_modal("compression"),
        )
        tk.Frame(eff_grid, bg=COL_BORDER_SUBTLE, width=1).grid(
            row=0, column=1, sticky="ns", pady=14,
        )
        self._build_eff_cell(
            eff_grid, 2, "AHORRO",
            sub_text="del flujo de bits",
            value_var=self.output_savings_var,
            on_click=lambda: self._show_efficacy_modal("savings"),
        )
        tk.Frame(eff_grid, bg=COL_BORDER_SUBTLE, width=1).grid(
            row=0, column=3, sticky="ns", pady=14,
        )
        self._build_eff_cell(
            eff_grid, 4, "VERIFICACION",
            sub_var=self.output_verify_sub_var,
            value_var=self.output_verify_var,
            on_click=lambda: self._show_efficacy_modal("verification"),
        )

        # --- Bits panel ---
        bits_eyebrow_row = tk.Frame(inner, bg=COL_BG)
        bits_eyebrow_row.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(
            bits_eyebrow_row, text="SECUENCIA DE BITS",
            style="Eyebrow.TLabel",
        ).pack(side=tk.LEFT)
        self._add_expand_link(
            bits_eyebrow_row, "VER COMPLETO  →", self._show_bits_modal,
        )
        self.output_bits_count_var = tk.StringVar(value="")
        ttk.Label(
            bits_eyebrow_row, textvariable=self.output_bits_count_var,
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT)

        bits_wrap = tk.Frame(inner, bg=COL_BORDER, highlightthickness=0)
        bits_wrap.grid(row=4, column=0, sticky="nsew", pady=(0, 20))

        self.bits_text = scrolledtext.ScrolledText(
            bits_wrap, wrap=tk.CHAR, font=(MONO_FAMILY, 11),
            bg=COL_SURFACE, fg=COL_INK, insertbackground=COL_INK,
            relief="flat", borderwidth=0, padx=18, pady=14,
            spacing1=2, spacing2=4, spacing3=2,
        )
        self.bits_text.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.bits_text.tag_configure("hint", foreground=COL_SUBTLE,
                                     font=(MONO_FAMILY, 9, "italic"))
        self.bits_text.tag_configure("note", foreground=COL_MUTED,
                                     font=(FONT_FAMILY, 9))

        # --- JSON metadata panel ---
        json_eyebrow_row = tk.Frame(inner, bg=COL_BG)
        json_eyebrow_row.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(
            json_eyebrow_row, text="METADATOS DEL CODIFICADO",
            style="Eyebrow.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(
            json_eyebrow_row,
            text="JSON. Lo que el decoder necesita para reconstruir el arbol.",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0))
        self._add_expand_link(
            json_eyebrow_row, "VER COMPLETO  →", self._show_json_modal,
            side=tk.RIGHT, padx=(0, 0),
        )

        json_wrap = tk.Frame(inner, bg=COL_BORDER, highlightthickness=0)
        json_wrap.grid(row=6, column=0, sticky="nsew")

        self.json_text = scrolledtext.ScrolledText(
            json_wrap, wrap=tk.WORD, font=(MONO_FAMILY, 9),
            bg=COL_SURFACE, fg=COL_INK, insertbackground=COL_INK,
            relief="flat", borderwidth=0, padx=14, pady=12,
        )
        self.json_text.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.json_text.tag_configure("hint", foreground=COL_SUBTLE,
                                     font=(MONO_FAMILY, 9, "italic"))

        # Estado vacio inicial.
        self._clear_output_panels()

    # ---- Output panels: helpers ----

    def _add_expand_link(self, parent: tk.Frame, text: str, on_click,
                         side=tk.LEFT, padx=(14, 0)) -> tk.Label:
        lbl = tk.Label(
            parent, text=text, bg=COL_BG, fg=COL_ACCENT,
            font=(FONT_FAMILY, 8, "bold"), cursor="hand2",
        )
        lbl.pack(side=side, padx=padx)
        lbl.bind("<Button-1>", lambda e: on_click())
        lbl.bind("<Enter>", lambda e: lbl.configure(fg=COL_ACCENT_HOVER))
        lbl.bind("<Leave>", lambda e: lbl.configure(fg=COL_ACCENT))
        return lbl

    def _build_eff_cell(self, parent: tk.Frame, col: int, label: str, *,
                        value_var: tk.StringVar,
                        sub_text: str | None = None,
                        sub_var: tk.StringVar | None = None,
                        on_click=None) -> None:
        cell = tk.Frame(parent, bg=COL_RAISED)
        cell.grid(row=0, column=col, sticky="nsew", padx=20, pady=14)

        head_row = tk.Frame(cell, bg=COL_RAISED)
        head_row.pack(fill=tk.X)
        tk.Label(
            head_row, text=label, bg=COL_RAISED, fg=COL_MUTED,
            font=(FONT_FAMILY, 8, "bold"),
        ).pack(side=tk.LEFT)
        if on_click is not None:
            tk.Label(
                head_row, text="→", bg=COL_RAISED, fg=COL_ACCENT,
                font=(FONT_FAMILY, 11, "bold"),
            ).pack(side=tk.RIGHT)

        tk.Label(
            cell, textvariable=value_var, bg=COL_RAISED, fg=COL_INK,
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(anchor="w", pady=(6, 0))
        if sub_var is not None:
            tk.Label(
                cell, textvariable=sub_var, bg=COL_RAISED, fg=COL_SUBTLE,
                font=(FONT_FAMILY, 9),
            ).pack(anchor="w", pady=(2, 0))
        elif sub_text is not None:
            tk.Label(
                cell, text=sub_text, bg=COL_RAISED, fg=COL_SUBTLE,
                font=(FONT_FAMILY, 9),
            ).pack(anchor="w", pady=(2, 0))

        if on_click is not None:
            for w in (cell, head_row, *cell.winfo_children(),
                      *head_row.winfo_children()):
                try:
                    w.configure(cursor="hand2")
                except tk.TclError:
                    pass
                w.bind("<Button-1>", lambda e, cb=on_click: cb(), add="+")

    def _add_chip(self, parent: tk.Frame, text: str, *,
                  accent: bool = False) -> None:
        bg = COL_ACCENT_SOFT if accent else COL_RAISED
        fg = COL_ACCENT_ACTIVE if accent else COL_INK
        chip = tk.Frame(parent, bg=bg)
        chip.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(
            chip, text=text, bg=bg, fg=fg,
            font=(FONT_FAMILY, 8, "bold"),
            padx=10, pady=5,
        ).pack()

    @staticmethod
    def _format_bit_stream(bits: str, group: int = 8,
                           per_line: int = 8) -> str:
        """Agrupa bits en bloques de 8 con espacio, y N bloques por linea."""
        if not bits:
            return ""
        chunks = [bits[i:i + group] for i in range(0, len(bits), group)]
        lines = []
        for i in range(0, len(chunks), per_line):
            lines.append(" ".join(chunks[i:i + per_line]))
        return "\n".join(lines)

    def _set_bits_panel(self, bits: str) -> None:
        bits = "".join((bits or "").split())
        self.bits_text.configure(state="normal")
        self.bits_text.delete("1.0", tk.END)
        if not bits:
            self.bits_text.insert(
                "1.0",
                "Codifica un archivo para ver aqui su secuencia de bits.\n",
                "hint",
            )
            self.output_bits_count_var.set("")
            self.bits_text.configure(state="disabled")
            return

        if len(bits) > DISPLAY_LIMIT:
            shown = self._format_bit_stream(bits[:DISPLAY_LIMIT])
            self.bits_text.insert("1.0", shown + "\n\n")
            self.bits_text.insert(
                tk.END,
                f"... {len(bits) - DISPLAY_LIMIT:,} bits mas. "
                "Usa 'Guardar codificado' o 'Copiar resultado' para "
                "obtener el flujo completo.\n",
                "note",
            )
            self.output_bits_count_var.set(
                f"{len(bits):,} bits  ·  mostrando {DISPLAY_LIMIT:,}"
            )
        else:
            self.bits_text.insert("1.0", self._format_bit_stream(bits))
            self.output_bits_count_var.set(f"{len(bits):,} bits")

        self.bits_text.configure(state="disabled")

    def _set_json_panel(self, payload: str) -> None:
        self.json_text.configure(state="normal")
        self.json_text.delete("1.0", tk.END)
        if not payload:
            self.json_text.insert(
                "1.0",
                "Aqui apareceran las frecuencias y los tamanos del codificado.\n",
                "hint",
            )
            self.json_text.configure(state="disabled")
            return

        try:
            parsed = json.loads(payload)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            pretty = payload

        if len(pretty) > DISPLAY_LIMIT:
            self.json_text.insert("1.0", pretty[:DISPLAY_LIMIT])
            self.json_text.insert(
                tk.END,
                f"\n\n... ({len(pretty) - DISPLAY_LIMIT:,} caracteres mas, "
                "truncado para visualizacion.)",
                "hint",
            )
        else:
            self.json_text.insert("1.0", pretty)

        self.json_text.configure(state="disabled")

    def _render_output_chips(self, header: str, json_payload: str,
                             bits: str) -> None:
        for w in self.output_chip_row.winfo_children():
            w.destroy()

        symbol_count = 0
        original_size = 0
        version = None
        if json_payload:
            try:
                parsed = json.loads(json_payload)
                symbol_count = len(parsed.get("frequencies", {}) or {})
                original_size = int(parsed.get("original_size") or 0)
                version = parsed.get("version")
            except Exception:
                pass

        format_label = (header or "SIN CABECERA").strip().upper()
        if version is not None:
            self._add_chip(self.output_chip_row,
                           f"{format_label} · v{version}", accent=True)
        else:
            self._add_chip(self.output_chip_row, format_label, accent=True)

        if bits:
            self._add_chip(self.output_chip_row, f"{len(bits):,} BITS")
        if symbol_count:
            self._add_chip(self.output_chip_row,
                           f"{symbol_count} SIMBOLOS")
        if original_size:
            self._add_chip(self.output_chip_row,
                           f"{original_size:,} B ORIGINALES")

    def _clear_output_panels(self) -> None:
        for w in self.output_chip_row.winfo_children():
            w.destroy()
        tk.Label(
            self.output_chip_row,
            text="Sin texto codificado todavia.",
            bg=COL_BG, fg=COL_SUBTLE, font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT)
        self.output_compression_var.set(EMPTY_VALUE)
        self.output_savings_var.set(EMPTY_VALUE)
        self.output_verify_var.set(EMPTY_VALUE)
        self.output_verify_sub_var.set("tras decodificar")
        self._set_bits_panel("")
        self._set_json_panel("")

    def _update_efficiency_strip(self, json_payload: str, bits: str) -> None:
        """Calcula TASA y AHORRO desde el JSON. La verificacion se actualiza
        aparte cuando se decodifica."""
        original_size = 0
        bit_length = 0
        if json_payload:
            try:
                parsed = json.loads(json_payload)
                original_size = int(parsed.get("original_size") or 0)
                bit_length = int(parsed.get("bit_length") or 0)
            except Exception:
                pass
        if not bit_length:
            bit_length = len(bits or "")

        if original_size > 0 and bit_length > 0:
            rate = bit_length / (original_size * 8) * 100
            self.output_compression_var.set(f"{rate:.1f} %")
            self.output_savings_var.set(f"{max(0.0, 100 - rate):.1f} %")
        else:
            self.output_compression_var.set(EMPTY_VALUE)
            self.output_savings_var.set(EMPTY_VALUE)

    def _update_verification(self) -> None:
        """Compara los bytes decodificados con el tamano original del JSON.

        Se llama tras `do_decode`. Si no hay decodificado todavia, deja la
        celda en estado pendiente.
        """
        if self.decoded_bytes is None or not self.encoded_text:
            self.output_verify_var.set(EMPTY_VALUE)
            self.output_verify_sub_var.set("tras decodificar")
            return

        parts = self.encoded_text.split("\n", 2)
        expected = 0
        if len(parts) >= 2:
            try:
                parsed = json.loads(parts[1])
                expected = int(parsed.get("original_size") or 0)
            except Exception:
                expected = 0

        got = len(self.decoded_bytes)
        if expected > 0:
            pct = got / expected * 100
            if got == expected:
                self.output_verify_var.set("100.0 % ✓")
            else:
                self.output_verify_var.set(f"{pct:.1f} %")
            self.output_verify_sub_var.set(
                f"{got:,} / {expected:,} bytes recuperados"
            )
        else:
            self.output_verify_var.set(f"{got:,} B")
            self.output_verify_sub_var.set("sin tamano de referencia")

    # ------------------------------------------------------------------
    # Tab: previsualizacion
    # ------------------------------------------------------------------

    def _build_preview_tab(self, nb: ttk.Notebook) -> None:
        frame = tk.Frame(nb, bg=COL_BG)
        nb.add(frame, text=" Vista previa ")

        inner = tk.Frame(frame, bg=COL_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        top = tk.Frame(inner, bg=COL_BG)
        top.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top, text="VISTA PREVIA",
                  style="Eyebrow.TLabel").pack(side=tk.LEFT, pady=(8, 0))
        ttk.Label(
            top,
            text="Representacion del archivo segun su formato (originales o decodificados).",
            style="Subhead.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0), pady=(8, 0))

        self.preview_info = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.preview_info,
                  style="Muted.TLabel").pack(side=tk.RIGHT, pady=(8, 0))

        wrap = tk.Frame(inner, bg=COL_BORDER, highlightthickness=0)
        wrap.pack(fill=tk.BOTH, expand=True)

        self.preview_canvas = tk.Canvas(
            wrap, bg=COL_SURFACE, highlightthickness=0,
        )
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.preview_canvas.bind("<Configure>", lambda e: self._refresh_preview())

        self.preview_controls = tk.Frame(inner, bg=COL_BG)
        self.preview_controls.pack(fill=tk.X, pady=(10, 0))

        self._preview_source: bytes | None = None
        self._preview_photo = None
        self._draw_preview_placeholder(
            "Carga un archivo, o codifica/decodifica uno, para verlo aqui."
        )

    # ------------------------------------------------------------------
    # Arbol: render
    # ------------------------------------------------------------------

    def _draw_tree_placeholder(self) -> None:
        c = self.tree_canvas
        c.delete("all")
        c.update_idletasks()
        w = max(c.winfo_width(), 1)
        h = max(c.winfo_height(), 1)
        c.create_text(
            w / 2, h / 2 - 10,
            text="Aun no hay arbol.",
            fill=COL_INK, font=(FONT_FAMILY, 13, "bold"),
        )
        c.create_text(
            w / 2, h / 2 + 16,
            text="Codifica o decodifica un archivo para visualizarlo aqui.",
            fill=COL_MUTED, font=(FONT_FAMILY, 10),
        )

    def _redraw_tree(self) -> None:
        if self.current_root is None:
            self._draw_tree_placeholder()
            return
        self._draw_tree(self.current_root)

    def _collect_positions(self, root: Node) -> tuple[dict, int]:
        positions: dict = {}
        counter = [0]
        max_depth = [0]

        def walk(node: Node, depth: int) -> None:
            if node is None:
                return
            walk(node.left, depth + 1)
            positions[id(node)] = (counter[0], depth, node)
            counter[0] += 1
            max_depth[0] = max(max_depth[0], depth)
            walk(node.right, depth + 1)

        walk(root, 0)
        return positions, max_depth[0]

    def _draw_tree(self, root: Node) -> None:
        canvas = self.tree_canvas
        canvas.delete("all")

        positions, max_depth = self._collect_positions(root)
        leaf_count = sum(1 for _, (_, _, n) in positions.items() if n.is_leaf)

        total = len(positions)
        NODE_LIMIT = 400
        truncated = total > NODE_LIMIT

        x_spacing = max(36, min(64, 920 // max(1, leaf_count)))
        y_spacing = 76
        margin_x, margin_y = 36, 36

        def xy(idx: int, depth: int) -> tuple[int, int]:
            return (margin_x + idx * x_spacing, margin_y + depth * y_spacing)

        drawable = set()
        if truncated:
            queue = [(root, 0)]
            while queue and len(drawable) < NODE_LIMIT:
                node, d = queue.pop(0)
                drawable.add(id(node))
                if node.left is not None:
                    queue.append((node.left, d + 1))
                if node.right is not None:
                    queue.append((node.right, d + 1))

        def show(node: Node) -> bool:
            return (not truncated) or id(node) in drawable

        def draw_edges(node: Node) -> None:
            if node is None or not show(node):
                return
            idx, depth, _ = positions[id(node)]
            x, y = xy(idx, depth)
            for child, label in ((node.left, "0"), (node.right, "1")):
                if child is None or not show(child):
                    continue
                cidx, cdepth, _ = positions[id(child)]
                cx, cy = xy(cidx, cdepth)
                canvas.create_line(x, y, cx, cy, fill=COL_TREE_EDGE, width=1.5)
                mx, my = (x + cx) / 2, (y + cy) / 2
                canvas.create_rectangle(mx - 8, my - 9, mx + 8, my + 9,
                                        fill=COL_SURFACE, outline="")
                canvas.create_text(mx, my, text=label, fill=COL_ACCENT,
                                   font=(FONT_FAMILY, 8, "bold"))
                draw_edges(child)

        draw_edges(root)

        r = 15
        for nid, (idx, depth, node) in positions.items():
            if not show(node):
                continue
            x, y = xy(idx, depth)
            if node.is_leaf:
                canvas.create_oval(x - r, y - r, x + r, y + r,
                                   fill=COL_TREE_LEAF, outline="")
                canvas.create_text(x, y, text=str(node.byte), fill="#FFFEFB",
                                   font=(FONT_FAMILY, 8, "bold"))
                canvas.create_text(x, y + r + 11,
                                   text=f"f={node.freq}", fill=COL_MUTED,
                                   font=(FONT_FAMILY, 8))
            else:
                canvas.create_oval(x - r, y - r, x + r, y + r,
                                   fill=COL_TREE_INNER, outline="")
                canvas.create_text(x, y, text=str(node.freq), fill=COL_INK,
                                   font=(FONT_FAMILY, 8, "bold"))

        width = margin_x * 2 + max(1, len(positions)) * x_spacing
        height = margin_y * 2 + (max_depth + 1) * y_spacing + 20
        canvas.configure(scrollregion=(0, 0, width, height))

        if truncated:
            canvas.create_text(
                margin_x, height - 14, anchor="nw",
                text=f"Arbol grande: mostrando {len(drawable)} de {total} nodos.",
                fill=COL_MUTED, font=(FONT_FAMILY, 8, "italic"),
            )

        self._tree_width = width
        self._tree_height = height

    def _center_tree(self) -> None:
        canvas = self.tree_canvas
        canvas.update_idletasks()
        total_w = getattr(self, "_tree_width", 0)
        total_h = getattr(self, "_tree_height", 0)
        view_w = max(1, canvas.winfo_width())
        view_h = max(1, canvas.winfo_height())
        if total_w > view_w:
            canvas.xview_moveto(max(0.0, (total_w - view_w) / 2 / total_w))
        else:
            canvas.xview_moveto(0.0)
        if total_h > view_h:
            canvas.yview_moveto(0.0)

    def _export_tree(self) -> None:
        if self.current_root is None:
            messagebox.showwarning(
                "Nada que exportar",
                "Codifica o decodifica un archivo primero.",
            )
            return
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            messagebox.showerror(
                "Falta Pillow",
                "Para exportar el arbol en PNG/JPEG instala Pillow:\n\n"
                "pip install Pillow",
            )
            return

        path = filedialog.asksaveasfilename(
            title="Exportar arbol de Huffman",
            defaultextension=".png",
            initialfile="huffman_tree.png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg")],
        )
        if not path:
            return

        try:
            img = self._render_tree_image(Image, ImageDraw, ImageFont)
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))
            return

        ext = Path(path).suffix.lower()
        try:
            if ext in (".jpg", ".jpeg"):
                img.convert("RGB").save(path, "JPEG", quality=92)
            else:
                img.save(path, "PNG")
        except OSError as e:
            messagebox.showerror("Error al guardar", str(e))
            return

        self._status(f"Arbol exportado: {path}", color=COL_OK)
        messagebox.showinfo("Exportado", f"Arbol guardado en:\n{path}")

    def _render_tree_image(self, Image, ImageDraw, ImageFont):
        root = self.current_root
        positions, max_depth = self._collect_positions(root)
        leaf_count = sum(1 for _, (_, _, n) in positions.items() if n.is_leaf)

        total = len(positions)
        NODE_LIMIT = 400
        truncated = total > NODE_LIMIT

        x_spacing = max(36, min(64, 920 // max(1, leaf_count)))
        y_spacing = 76
        margin_x, margin_y = 36, 36

        drawable = set()
        if truncated:
            queue = [(root, 0)]
            while queue and len(drawable) < NODE_LIMIT:
                node, d = queue.pop(0)
                drawable.add(id(node))
                if node.left is not None:
                    queue.append((node.left, d + 1))
                if node.right is not None:
                    queue.append((node.right, d + 1))

        def show(n) -> bool:
            return (not truncated) or id(n) in drawable

        def xy(idx: int, depth: int) -> tuple[int, int]:
            return (margin_x + idx * x_spacing, margin_y + depth * y_spacing)

        width = margin_x * 2 + max(1, len(positions)) * x_spacing
        height = margin_y * 2 + (max_depth + 1) * y_spacing + 30

        img = Image.new("RGB", (width, height), COL_SURFACE)
        draw = ImageDraw.Draw(img)

        def load_font(size: int, bold: bool = False):
            for name in ("segoeuib" if bold else "segoeui",
                         "arialbd" if bold else "arial",
                         "DejaVuSans-Bold" if bold else "DejaVuSans"):
                try:
                    return ImageFont.truetype(f"{name}.ttf", size)
                except (OSError, IOError):
                    pass
            return ImageFont.load_default()

        f_leaf = load_font(11, bold=True)
        f_inner = load_font(10, bold=True)
        f_edge = load_font(10, bold=True)
        f_small = load_font(9)

        def draw_edges(node) -> None:
            if node is None or not show(node):
                return
            idx, depth, _ = positions[id(node)]
            x, y = xy(idx, depth)
            for child, label in ((node.left, "0"), (node.right, "1")):
                if child is None or not show(child):
                    continue
                cidx, cdepth, _ = positions[id(child)]
                cx, cy = xy(cidx, cdepth)
                draw.line((x, y, cx, cy), fill=COL_TREE_EDGE, width=2)
                mx, my = (x + cx) // 2, (y + cy) // 2
                draw.rectangle((mx - 9, my - 10, mx + 9, my + 10),
                               fill=COL_SURFACE, outline=COL_SURFACE)
                tw = draw.textlength(label, font=f_edge)
                draw.text((mx - tw / 2, my - 7), label,
                          fill=COL_ACCENT, font=f_edge)
                draw_edges(child)

        draw_edges(root)

        r = 17
        for nid, (idx, depth, node) in positions.items():
            if not show(node):
                continue
            x, y = xy(idx, depth)
            color = COL_TREE_LEAF if node.is_leaf else COL_TREE_INNER
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
            text = str(node.byte) if node.is_leaf else str(node.freq)
            font = f_leaf if node.is_leaf else f_inner
            text_color = COL_SURFACE if node.is_leaf else COL_INK
            tw = draw.textlength(text, font=font)
            draw.text((x - tw / 2, y - r / 2 - 2), text,
                      fill=text_color, font=font)
            if node.is_leaf:
                sub = f"f={node.freq}"
                tw = draw.textlength(sub, font=f_small)
                draw.text((x - tw / 2, y + r + 4), sub,
                          fill=COL_MUTED, font=f_small)

        if truncated:
            draw.text(
                (margin_x, height - 20),
                f"Arbol grande: mostrando {len(drawable)} de {total} nodos.",
                fill=COL_MUTED, font=f_small,
            )
        return img

    # ------------------------------------------------------------------
    # Helpers de UI
    # ------------------------------------------------------------------

    def _reset_steps(self) -> None:
        self.stepper.reset()

    def _mark_step(self, n: int) -> None:
        if 1 <= n <= len(self.stepper.steps):
            self.stepper.mark_active(n - 1)

    def log(self, line: str) -> None:
        stripped = line.strip()
        tag = "sub"
        if stripped.startswith("Paso "):
            tag = "step"
            try:
                n = int(stripped.split()[1].rstrip(":"))
                self._mark_step(n)
            except (ValueError, IndexError):
                pass
        elif stripped.startswith("=="):
            tag = "step"
        elif "completada" in stripped.lower():
            tag = "ok"
        elif "ADVERTENCIA" in stripped:
            tag = "warn"
        self.log_text.insert(tk.END, line + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()

    def _set_output(self, text: str) -> None:
        """Pone el texto codificado en los paneles estructurados.

        Formato esperado: tres lineas (cabecera, JSON, bitstream). Si la
        entrada no las trae, se pueblan los paneles con lo que haya.
        """
        text = (text or "").strip()
        if not text:
            self._clear_output_panels()
            return

        parts = text.split("\n", 2)
        header = parts[0].strip() if parts else ""
        json_payload = parts[1] if len(parts) > 1 else ""
        bits = parts[2] if len(parts) > 2 else ""

        self._render_output_chips(header, json_payload, bits)
        self._update_efficiency_strip(json_payload, bits)
        self._update_verification()
        self._set_bits_panel(bits)
        self._set_json_panel(json_payload)

    def _paste_encoded_dialog(self) -> None:
        """Abre un Toplevel con un textarea para pegar texto codificado crudo."""
        win = tk.Toplevel(self.root)
        win.title("Pegar texto codificado")
        win.configure(bg=COL_BG)
        win.transient(self.root)
        win.minsize(620, 420)

        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        ww, wh = 720, 540
        x = rx + (rw - ww) // 2
        y = ry + (rh - wh) // 2
        win.geometry(f"{ww}x{wh}+{max(0, x)}+{max(0, y)}")

        head = tk.Frame(win, bg=COL_BG)
        head.pack(fill=tk.X, padx=24, pady=(20, 8))
        ttk.Label(head, text="PEGAR TEXTO CRUDO",
                  style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(
            head,
            text=f"Pega aqui el contenido completo de un .txt codificado, "
                 f"empezando por '{FORMAT_HEADER}'.",
            style="Subhead.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        tk.Frame(win, bg=COL_BORDER_SUBTLE, height=1).pack(
            fill=tk.X, padx=24, pady=(12, 0)
        )

        body = tk.Frame(win, bg=COL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=14)
        paste_wrap = tk.Frame(body, bg=COL_BORDER, highlightthickness=0)
        paste_wrap.pack(fill=tk.BOTH, expand=True)
        txt = scrolledtext.ScrolledText(
            paste_wrap, wrap=tk.CHAR, font=(MONO_FAMILY, 9),
            bg=COL_SURFACE, fg=COL_INK, insertbackground=COL_INK,
            relief="flat", borderwidth=0, padx=14, pady=12,
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        txt.focus_set()

        try:
            clip = self.root.clipboard_get()
            if clip and clip.strip().startswith(FORMAT_HEADER):
                txt.insert("1.0", clip)
        except tk.TclError:
            pass

        foot = tk.Frame(win, bg=COL_BG)
        foot.pack(fill=tk.X, padx=24, pady=(0, 20))

        def confirm() -> None:
            content = txt.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning(
                    "Vacio", "Pega contenido primero.",
                )
                return
            if not content.startswith(FORMAT_HEADER):
                if not messagebox.askyesno(
                    "Cabecera no reconocida",
                    f"El texto no empieza con '{FORMAT_HEADER}'. "
                    "¿Cargarlo de todos modos?",
                ):
                    return
            self.encoded_text = content
            self.encoded_source_path = None
            self.loaded_path = None
            self.loaded_bytes = None
            self.decoded_bytes = None
            self.info_var.set(
                f"Texto pegado  ·  {len(content):,} caracteres codificados"
            )
            self._set_output(content)
            self._set_preview(None)
            self.current_metrics = None
            self._refresh_analysis()
            self._status(
                "Texto codificado cargado. Pulsa 'Decodificar'.",
                color=COL_OK,
            )
            win.destroy()

        RoundedButton(
            foot, text="Cargar", command=confirm, bold=True,
            bg=COL_ACCENT, fg="#FFFFFF",
            hover_bg=COL_ACCENT_HOVER, active_bg=COL_ACCENT_ACTIVE,
            parent_bg=COL_BG, padx=22, pady=10,
        ).pack(side=tk.RIGHT)
        RoundedButton(
            foot, text="Cancelar", command=win.destroy,
            bg=COL_BG, fg=COL_MUTED,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=18, pady=10,
        ).pack(side=tk.RIGHT, padx=(0, 8))

        win.bind("<Escape>", lambda e: win.destroy())

    def _status(self, msg: str, color: str = COL_OK) -> None:
        self.status_var.set(msg)
        self._draw_status_dot(color)

    def _update_metrics(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if k in self.metric_vars:
                self.metric_vars[k].set(v)

    def _draw_preview_placeholder(self, msg: str) -> None:
        c = self.preview_canvas
        c.delete("all")
        c.update_idletasks()
        w = max(c.winfo_width(), 1)
        h = max(c.winfo_height(), 1)
        c.create_text(
            w / 2, h / 2 - 8, text="Sin vista previa",
            fill=COL_INK, font=(FONT_FAMILY, 13, "bold"),
        )
        c.create_text(
            w / 2, h / 2 + 16, text=msg,
            fill=COL_MUTED, font=(FONT_FAMILY, 10), width=w - 80,
        )
        self.preview_info.set("")

    def _set_preview(self, data: bytes | None) -> None:
        self._preview_source = data
        self._stop_media_playback()
        self._clear_preview_controls()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        data = self._preview_source
        if not data:
            self._draw_preview_placeholder(
                "Carga un archivo, o codifica/decodifica uno, para verlo aqui."
            )
            return

        # En un evento de resize, los motores activos siguen vivos y solo
        # redibujamos lo necesario sin reiniciar la reproduccion.
        if self._video_cap is not None:
            return  # el bucle de fotogramas reescala con el nuevo tamano
        if self._pdf_doc is not None:
            self._render_pdf_page(len(data))
            return
        if self._audio_temp_path is not None:
            ext_active = self._audio_temp_path.suffix or ".mp3"
            self._draw_audio_visual(data, ext_active)
            return

        ext = self._sniff_extension(data)

        if ext in (".png", ".jpg", ".gif", ".bmp", ".webp", ".tif"):
            self._draw_image_preview(data, ext)
        elif ext == ".pdf":
            self._draw_pdf_preview(data)
        elif ext in (".mp3", ".wav", ".flac", ".ogg", ".m4a"):
            self._draw_audio_preview(data, ext)
        elif ext in (".mp4", ".webm", ".avi"):
            self._draw_video_preview(data, ext)
        elif ext == ".txt":
            self._draw_text_preview(data)
        else:
            self._draw_binary_preview(data)

    # ------------------------------------------------------------------
    # Reproduccion de medios: utilidades comunes
    # ------------------------------------------------------------------

    def _media_temp_dir_path(self) -> Path:
        if self._media_temp_dir is None:
            self._media_temp_dir = Path(tempfile.mkdtemp(prefix="milloxcoder_"))
        return self._media_temp_dir

    def _write_media_temp(self, data: bytes, ext: str) -> Path:
        path = self._media_temp_dir_path() / f"preview{ext}"
        path.write_bytes(data)
        return path

    def _clear_preview_controls(self) -> None:
        for child in self.preview_controls.winfo_children():
            child.destroy()

    def _stop_media_playback(self) -> None:
        # Audio
        if self._audio_initialized:
            try:
                import pygame
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
        self._audio_paused = False
        self._audio_temp_path = None

        # Video
        if self._video_after_id is not None:
            try:
                self.root.after_cancel(self._video_after_id)
            except Exception:
                pass
            self._video_after_id = None
        if self._video_cap is not None:
            try:
                self._video_cap.release()
            except Exception:
                pass
            self._video_cap = None
        self._video_playing = False
        self._video_photo = None
        self._video_temp_path = None

        # PDF
        if self._pdf_doc is not None:
            try:
                self._pdf_doc.close()
            except Exception:
                pass
            self._pdf_doc = None
        self._pdf_page_idx = 0
        self._pdf_total_pages = 0
        self._pdf_label_var = None

    def _on_close(self) -> None:
        self._stop_media_playback()
        if self._audio_initialized:
            try:
                import pygame
                pygame.mixer.quit()
            except Exception:
                pass
            self._audio_initialized = False
        if self._media_temp_dir is not None:
            shutil.rmtree(self._media_temp_dir, ignore_errors=True)
            self._media_temp_dir = None
        self.root.destroy()

    def _preview_canvas_dims(self) -> tuple[tk.Canvas, int, int]:
        c = self.preview_canvas
        c.delete("all")
        c.update_idletasks()
        return c, max(c.winfo_width(), 1), max(c.winfo_height(), 1)

    def _draw_format_chip(self, c: tk.Canvas, x: float, y: float,
                          label: str) -> None:
        text_id = c.create_text(
            x, y, text=label, fill=COL_ACCENT_ACTIVE,
            font=(FONT_FAMILY, 9, "bold"), anchor="center",
        )
        bbox = c.bbox(text_id)
        if not bbox:
            return
        pad_x, pad_y = 12, 5
        rect = c.create_rectangle(
            bbox[0] - pad_x, bbox[1] - pad_y,
            bbox[2] + pad_x, bbox[3] + pad_y,
            fill=COL_ACCENT_SOFT, outline="",
        )
        c.tag_raise(text_id, rect)

    def _draw_image_preview(self, data: bytes, ext: str) -> None:
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self._draw_preview_placeholder(
                "Instala Pillow (pip install Pillow) para previsualizar la imagen."
            )
            return

        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception:
            self._draw_binary_preview(data)
            return

        c, cw, ch = self._preview_canvas_dims()
        iw, ih = img.size
        scale = min((cw - 24) / iw, (ch - 24) / ih, 1.0)
        if scale < 1.0:
            new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
            display_img = img.resize(new_size, Image.LANCZOS)
        else:
            display_img = img

        self._preview_photo = ImageTk.PhotoImage(display_img)
        c.create_image(cw / 2, ch / 2, image=self._preview_photo, anchor="center")
        self.preview_info.set(
            f"{img.format or '?'}  ·  {iw}×{ih} px  ·  {len(data):,} bytes"
        )

    def _draw_audio_preview(self, data: bytes, ext: str) -> None:
        self._draw_audio_visual(data, ext)
        self._build_audio_controls(data, ext)
        self.preview_info.set(
            f"Audio  ·  {ext.lstrip('.').upper()}  ·  {len(data):,} bytes"
        )

    def _draw_audio_visual(self, data: bytes, ext: str) -> None:
        c, cw, ch = self._preview_canvas_dims()
        kind = ext.lstrip(".").upper()
        self._draw_format_chip(c, cw / 2, 28, f"AUDIO · {kind}")

        n = len(data)
        margin_x = max(56, int(cw * 0.10))
        plot_w = max(120, cw - 2 * margin_x)
        plot_h = max(60, int(ch * 0.42))
        cy = ch / 2 + 8

        bar_w = 3
        gap = 2
        n_bars = max(20, plot_w // (bar_w + gap))

        skip = min(2048, n // 16) if n > 4096 else 0
        body = data[skip:] if (n - skip) > n_bars * 4 else data
        step = max(1, len(body) // max(1, n_bars))

        total_w = n_bars * (bar_w + gap) - gap
        x = (cw - total_w) / 2
        for i in range(n_bars):
            idx = i * step
            sample = body[idx] if idx < len(body) else 128
            amp = abs(sample - 128) / 128.0
            h = max(3, int(amp * plot_h))
            color = COL_ACCENT if i % 9 == 0 else COL_INK
            c.create_rectangle(
                x, cy - h / 2, x + bar_w, cy + h / 2,
                fill=color, outline="",
            )
            x += bar_w + gap

        c.create_line(
            margin_x, cy + plot_h / 2 + 18,
            cw - margin_x, cy + plot_h / 2 + 18,
            fill=COL_BORDER, width=1,
        )

    def _build_audio_controls(self, data: bytes, ext: str) -> None:
        self._clear_preview_controls()
        bar = self.preview_controls

        try:
            import pygame  # noqa: F401
            playable = True
            note = ""
        except ImportError:
            playable = False
            note = "Instala 'pygame-ce' para reproducir el audio aqui."

        if not playable:
            ttk.Label(bar, text=note, style="Muted.TLabel").pack(side=tk.LEFT)
            return

        try:
            self._audio_temp_path = self._write_media_temp(data, ext)
        except OSError as e:
            ttk.Label(
                bar, text=f"No se pudo preparar el audio: {e}",
                style="Muted.TLabel",
            ).pack(side=tk.LEFT)
            return

        RoundedButton(
            bar, "Reproducir", command=self._audio_play,
            bg=COL_ACCENT, fg="#FFFFFF",
            hover_bg=COL_ACCENT_HOVER, active_bg=COL_ACCENT_ACTIVE,
            parent_bg=COL_BG, padx=14, pady=8, bold=True,
        ).pack(side=tk.LEFT)
        RoundedButton(
            bar, "Pausa", command=self._audio_toggle_pause,
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT, padx=(8, 0))
        RoundedButton(
            bar, "Detener", command=self._audio_stop,
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _ensure_audio_engine(self) -> bool:
        try:
            import pygame
        except ImportError:
            return False
        if not self._audio_initialized:
            try:
                pygame.mixer.init()
            except Exception as e:
                messagebox.showerror(
                    "Audio no disponible",
                    f"No se pudo inicializar pygame.mixer: {e}",
                )
                return False
            self._audio_initialized = True
        return True

    def _audio_play(self) -> None:
        if self._audio_temp_path is None:
            return
        if not self._ensure_audio_engine():
            return
        import pygame
        try:
            pygame.mixer.music.load(str(self._audio_temp_path))
            pygame.mixer.music.play()
            self._audio_paused = False
        except pygame.error as e:
            messagebox.showerror(
                "Reproduccion fallida",
                f"pygame no pudo decodificar el audio: {e}",
            )

    def _audio_toggle_pause(self) -> None:
        if not self._audio_initialized:
            return
        import pygame
        if self._audio_paused:
            pygame.mixer.music.unpause()
            self._audio_paused = False
        else:
            pygame.mixer.music.pause()
            self._audio_paused = True

    def _audio_stop(self) -> None:
        if not self._audio_initialized:
            return
        import pygame
        pygame.mixer.music.stop()
        self._audio_paused = False

    def _draw_video_preview(self, data: bytes, ext: str) -> None:
        kind = ext.lstrip(".").upper()
        try:
            import cv2  # noqa: F401
        except ImportError:
            self._draw_video_static(data, ext, reason=(
                "Instala 'opencv-python' para reproducir el video aqui."
            ))
            return

        try:
            self._video_temp_path = self._write_media_temp(data, ext)
        except OSError as e:
            self._draw_video_static(data, ext, reason=f"No se pudo preparar el video: {e}")
            return

        import cv2
        cap = cv2.VideoCapture(str(self._video_temp_path))
        if not cap.isOpened():
            cap.release()
            self._draw_video_static(
                data, ext,
                reason="OpenCV no pudo abrir el video (codec no soportado).",
            )
            return

        self._video_cap = cap
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._video_frame_delay = max(15, int(1000 / fps))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        c, cw, ch = self._preview_canvas_dims()
        self._draw_format_chip(c, cw / 2, 28, f"VIDEO · {kind}")
        self._show_video_frame(initial=True)

        self._build_video_controls()
        info_extra = f"  ·  {total} frames" if total else ""
        self.preview_info.set(
            f"Video  ·  {kind}  ·  {fps:.0f} fps{info_extra}  ·  {len(data):,} bytes"
        )

    def _build_video_controls(self) -> None:
        self._clear_preview_controls()
        bar = self.preview_controls

        RoundedButton(
            bar, "Reproducir", command=self._video_play,
            bg=COL_ACCENT, fg="#FFFFFF",
            hover_bg=COL_ACCENT_HOVER, active_bg=COL_ACCENT_ACTIVE,
            parent_bg=COL_BG, padx=14, pady=8, bold=True,
        ).pack(side=tk.LEFT)
        RoundedButton(
            bar, "Pausa", command=self._video_pause,
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT, padx=(8, 0))
        RoundedButton(
            bar, "Detener", command=self._video_stop,
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _show_video_frame(self, initial: bool = False) -> None:
        if self._video_cap is None:
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return
        import cv2

        ret, frame = self._video_cap.read()
        if not ret:
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._video_cap.read()
            if not ret:
                self._video_pause()
                return

        c = self.preview_canvas
        cw = max(c.winfo_width(), 1)
        ch = max(c.winfo_height(), 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ih, iw = rgb.shape[:2]
        scale = min((cw - 32) / iw, (ch - 80) / ih, 1.0)
        if scale < 1.0:
            new_w = max(1, int(iw * scale))
            new_h = max(1, int(ih * scale))
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        img = Image.fromarray(rgb)
        self._video_photo = ImageTk.PhotoImage(img)

        c.delete("video_frame")
        c.create_image(cw / 2, ch / 2 + 8, image=self._video_photo,
                       anchor="center", tags="video_frame")

        if self._video_playing and not initial:
            self._video_after_id = self.root.after(
                self._video_frame_delay, self._show_video_frame
            )

    def _video_play(self) -> None:
        if self._video_cap is None or self._video_playing:
            return
        self._video_playing = True
        self._video_after_id = self.root.after(
            self._video_frame_delay, self._show_video_frame
        )

    def _video_pause(self) -> None:
        self._video_playing = False
        if self._video_after_id is not None:
            try:
                self.root.after_cancel(self._video_after_id)
            except Exception:
                pass
            self._video_after_id = None

    def _video_stop(self) -> None:
        self._video_pause()
        if self._video_cap is None:
            return
        import cv2
        self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._show_video_frame(initial=True)

    def _draw_video_static(self, data: bytes, ext: str,
                           reason: str = "") -> None:
        c, cw, ch = self._preview_canvas_dims()
        self._clear_preview_controls()
        kind = ext.lstrip(".").upper()
        self._draw_format_chip(c, cw / 2, 28, f"VIDEO · {kind}")

        strip_h = max(120, min(int(ch * 0.42), 200))
        strip_w = min(cw - 80, 560)
        sx = (cw - strip_w) / 2
        sy = ch / 2 - strip_h / 2 + 4
        band = 16

        c.create_rectangle(sx, sy, sx + strip_w, sy + band,
                           fill=COL_INK, outline="")
        c.create_rectangle(sx, sy + strip_h - band, sx + strip_w,
                           sy + strip_h, fill=COL_INK, outline="")

        holes = 9
        hole_w = 18
        gap_h = (strip_w - holes * hole_w) / (holes + 1)
        for i in range(holes):
            hx = sx + gap_h + i * (hole_w + gap_h)
            c.create_rectangle(hx, sy + 4, hx + hole_w, sy + band - 4,
                               fill=COL_BG, outline="")
            c.create_rectangle(hx, sy + strip_h - band + 4,
                               hx + hole_w, sy + strip_h - 4,
                               fill=COL_BG, outline="")

        frames = 3
        inner_top = sy + band + 8
        inner_bot = sy + strip_h - band - 8
        inner_h = inner_bot - inner_top
        pad = 12
        frame_w = (strip_w - pad * (frames + 1)) / frames
        for i in range(frames):
            fx = sx + pad + i * (frame_w + pad)
            c.create_rectangle(fx, inner_top, fx + frame_w, inner_bot,
                               fill=COL_RAISED, outline=COL_BORDER, width=1)
            cx = fx + frame_w / 2
            cyf = inner_top + inner_h / 2
            r = min(frame_w, inner_h) * 0.18
            c.create_polygon(
                cx - r * 0.7, cyf - r,
                cx - r * 0.7, cyf + r,
                cx + r, cyf,
                fill=COL_ACCENT, outline="",
            )

        if reason:
            c.create_text(
                cw / 2, ch - 26, text=reason,
                fill=COL_MUTED, font=(FONT_FAMILY, 9), width=cw - 80,
            )
        self.preview_info.set(f"Video  ·  {kind}  ·  {len(data):,} bytes")

    def _draw_pdf_preview(self, data: bytes) -> None:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            self._draw_pdf_static(data, reason=(
                "Instala 'pymupdf' para renderizar paginas reales (pip install pymupdf)."
            ))
            return

        try:
            self._pdf_doc = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            self._draw_pdf_static(
                data, reason=f"PDF no decodificable: {e}"
            )
            return

        self._pdf_total_pages = self._pdf_doc.page_count
        self._pdf_page_idx = 0
        self._clear_preview_controls()
        self._pdf_label_var = tk.StringVar(value="")
        self._build_pdf_controls()
        self._render_pdf_page(len(data))

    def _build_pdf_controls(self) -> None:
        bar = self.preview_controls
        RoundedButton(
            bar, "<- Anterior",
            command=lambda: self._pdf_step(-1),
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT)
        RoundedButton(
            bar, "Siguiente ->",
            command=lambda: self._pdf_step(1),
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(bar, textvariable=self._pdf_label_var,
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=(16, 0))

    def _pdf_step(self, delta: int) -> None:
        if self._pdf_doc is None or self._pdf_total_pages == 0:
            return
        self._pdf_page_idx = max(
            0, min(self._pdf_total_pages - 1, self._pdf_page_idx + delta)
        )
        self._render_pdf_page(len(self._preview_source or b""))

    def _render_pdf_page(self, byte_size: int) -> None:
        if self._pdf_doc is None:
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self._draw_pdf_static(self._preview_source or b"", reason=(
                "Instala Pillow para renderizar las paginas."
            ))
            return

        c, cw, ch = self._preview_canvas_dims()
        self._draw_format_chip(c, cw / 2, 28, "PDF")

        page = self._pdf_doc[self._pdf_page_idx]
        page_rect = page.rect
        target_w = max(60, cw - 80)
        target_h = max(60, ch - 100)
        scale = min(target_w / max(page_rect.width, 1),
                    target_h / max(page_rect.height, 1))
        scale = max(scale, 0.25)

        import fitz
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self._preview_photo = ImageTk.PhotoImage(img)
        c.create_image(cw / 2, ch / 2 + 8, image=self._preview_photo,
                       anchor="center")

        if self._pdf_label_var is not None:
            self._pdf_label_var.set(
                f"Pag. {self._pdf_page_idx + 1} / {self._pdf_total_pages}"
            )
        version = self._pdf_doc.metadata.get("format", "PDF")
        self.preview_info.set(
            f"{version}  ·  {self._pdf_total_pages} pag.  ·  {byte_size:,} bytes"
        )

    def _draw_pdf_static(self, data: bytes, reason: str = "") -> None:
        c, cw, ch = self._preview_canvas_dims()
        self._clear_preview_controls()
        self._draw_format_chip(c, cw / 2, 28, "PDF")

        doc_w = min(cw - 140, 220)
        doc_h = min(ch - 140, 280)
        if doc_w < 100 or doc_h < 120:
            doc_w, doc_h = 160, 200
        dx = cw / 2 - doc_w / 2
        dy = ch / 2 - doc_h / 2 + 8
        fold = 32

        c.create_polygon(
            dx, dy,
            dx + doc_w - fold, dy,
            dx + doc_w, dy + fold,
            dx + doc_w, dy + doc_h,
            dx, dy + doc_h,
            fill=COL_SURFACE, outline=COL_INK, width=2,
        )
        c.create_polygon(
            dx + doc_w - fold, dy,
            dx + doc_w, dy + fold,
            dx + doc_w - fold, dy + fold,
            fill=COL_RAISED, outline=COL_INK, width=2,
        )

        line_y = dy + fold + 22
        line_idx = 0
        while line_y < dy + doc_h - 20:
            line_w = doc_w - 36
            if line_idx % 4 == 3:
                line_w *= 0.55
            c.create_rectangle(
                dx + 18, line_y, dx + 18 + line_w, line_y + 5,
                fill=COL_BORDER, outline="",
            )
            line_y += 14
            line_idx += 1

        if reason:
            c.create_text(
                cw / 2, ch - 28, text=reason,
                fill=COL_MUTED, font=(FONT_FAMILY, 9), width=cw - 80,
            )
        self.preview_info.set(f"PDF  ·  {len(data):,} bytes")

    def _draw_text_preview(self, data: bytes) -> None:
        c, cw, ch = self._preview_canvas_dims()
        self._draw_format_chip(c, cw / 2, 28, "TEXTO")

        try:
            text = data.decode("utf-8")
            encoding = "UTF-8"
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")
            encoding = "Latin-1"

        snippet = text[:3000]
        if len(text) > 3000:
            snippet = snippet.rstrip() + "\n\n..."

        margin = 32
        c.create_text(
            margin, 60,
            text=snippet, fill=COL_INK,
            font=(MONO_FAMILY, 9), anchor="nw",
            width=cw - margin * 2,
        )

        lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        self.preview_info.set(
            f"Texto  ·  {encoding}  ·  {lines:,} lineas  ·  {len(data):,} bytes"
        )

    def _draw_binary_preview(self, data: bytes) -> None:
        c, cw, ch = self._preview_canvas_dims()
        self._draw_format_chip(c, cw / 2, 28, "BINARIO")

        sample = data[:128]
        rows = []
        for i in range(0, len(sample), 16):
            chunk = sample[i:i + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(
                chr(b) if 32 <= b < 127 else "·" for b in chunk
            )
            rows.append(f"{i:04x}  {hex_part:<47}  {ascii_part}")

        body = "\n".join(rows) if rows else "(vacio)"
        c.create_text(
            cw / 2, ch / 2,
            text=body, fill=COL_INK,
            font=(MONO_FAMILY, 9), anchor="center",
        )
        c.create_text(
            cw / 2, ch - 26,
            text="Formato no reconocido. Mostrando los primeros bytes en hexadecimal.",
            fill=COL_MUTED, font=(FONT_FAMILY, 9),
        )
        self.preview_info.set(f"Binario  ·  {len(data):,} bytes")

    def _capture_tree(self, root: Node, codes: dict, freqs: dict) -> None:
        self.current_root = root
        self.current_codes = codes
        self.current_freqs = freqs
        self._redraw_tree()
        self.root.after(50, self._center_tree)

    # ------------------------------------------------------------------
    # Dashboard de analisis: refresh
    # ------------------------------------------------------------------

    def _refresh_analysis(self) -> None:
        m = self.current_metrics
        if not m:
            # mostrar empty state
            self.analysis_content.pack_forget()
            self.analysis_empty.pack(fill=tk.BOTH, expand=True)
            return

        # ocultar empty, mostrar contenido
        self.analysis_empty.pack_forget()
        self.analysis_content.pack(fill=tk.BOTH, expand=True)

        H = m["entropy"]
        L = m["mean_length"]
        R = m["redundancy"]
        eta = m["efficiency"]

        self.analysis_vars["H"].set(f"{H:.4f}")
        self.analysis_vars["L"].set(f"{L:.4f}")
        self.analysis_vars["R"].set(f"{R:+.4f}")
        self.analysis_vars["eta"].set(f"{eta * 100:.2f} %")
        self.analysis_vars["sigma2"].set(f"{m['variance']:.4f}")
        self.analysis_vars["sigma"].set(f"{m['std_dev']:.4f}")
        self.analysis_vars["min_len"].set(str(m["min_code_len"]))
        self.analysis_vars["max_len"].set(str(m["max_code_len"]))

        src = (
            f"{self.last_action_label}  ·  "
            f"{m['total_symbols']:,} bytes totales  ·  "
            f"{m['unique_symbols']:,} simbolos unicos"
        )
        self.analysis_source_var.set(src)

        self._draw_compare()
        self._draw_distribution()

    # ------------------------------------------------------------------
    # Modal de calculo paso a paso
    # ------------------------------------------------------------------

    _METRIC_TITLES = {
        "H":       ("Entropia",            "H"),
        "L":       ("Longitud media",      "L"),
        "R":       ("Redundancia",         "R"),
        "eta":     ("Eficiencia",          "η"),
        "sigma2":  ("Varianza de longitud", "σ²"),
        "sigma":   ("Desviacion estandar",  "σ"),
        "min_len": ("Codigo mas corto",    "min |c|"),
        "max_len": ("Codigo mas largo",    "max |c|"),
    }

    def _show_calc_modal(self, key: str) -> None:
        m = self.current_metrics
        if not m:
            messagebox.showinfo(
                "Sin datos",
                "Codifica o decodifica un archivo para ver los calculos.",
            )
            return

        title, symbol = self._METRIC_TITLES.get(key, (key, key))

        win = tk.Toplevel(self.root)
        win.title(f"Calculo · {title}")
        win.configure(bg=COL_BG)
        win.transient(self.root)
        win.minsize(720, 540)

        # Center on parent
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        ww, wh = 800, 600
        x = rx + (rw - ww) // 2
        y = ry + (rh - wh) // 2
        win.geometry(f"{ww}x{wh}+{max(0, x)}+{max(0, y)}")

        # Header
        head = tk.Frame(win, bg=COL_BG)
        head.pack(fill=tk.X, padx=24, pady=(20, 8))

        eyebrow = tk.Label(
            head, text=title.upper(), bg=COL_BG, fg=COL_MUTED,
            font=(FONT_FAMILY, 8, "bold"),
        )
        eyebrow.pack(anchor="w")

        symbol_row = tk.Frame(head, bg=COL_BG)
        symbol_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            symbol_row, text=symbol, bg=COL_BG, fg=COL_ACCENT,
            font=(FONT_FAMILY, 22, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            symbol_row, text=f"  {title}", bg=COL_BG, fg=COL_INK,
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(side=tk.LEFT)

        # Rule
        tk.Frame(win, bg=COL_BORDER_SUBTLE, height=1).pack(
            fill=tk.X, padx=24, pady=(12, 0)
        )

        # Body (scrollable text)
        body_wrap = tk.Frame(win, bg=COL_BG)
        body_wrap.pack(fill=tk.BOTH, expand=True, padx=24, pady=(14, 12))

        text = scrolledtext.ScrolledText(
            body_wrap, wrap=tk.WORD, font=(MONO_FAMILY, 10),
            bg=COL_SURFACE, fg=COL_INK,
            relief="flat", borderwidth=0, padx=18, pady=16,
            highlightthickness=1, highlightbackground=COL_BORDER,
        )
        text.pack(fill=tk.BOTH, expand=True)

        # Tags
        text.tag_configure(
            "h1", foreground=COL_INK,
            font=(FONT_FAMILY, 12, "bold"), spacing1=6, spacing3=6,
        )
        text.tag_configure(
            "eyebrow", foreground=COL_MUTED,
            font=(FONT_FAMILY, 8, "bold"), spacing1=10, spacing3=4,
        )
        text.tag_configure(
            "formula", foreground=COL_ACCENT,
            font=(MONO_FAMILY, 11, "bold"), spacing1=4, spacing3=8,
        )
        text.tag_configure("body", foreground=COL_INK, font=(MONO_FAMILY, 10))
        text.tag_configure("muted", foreground=COL_MUTED, font=(MONO_FAMILY, 9))
        text.tag_configure(
            "accent", foreground=COL_ACCENT,
            font=(MONO_FAMILY, 10, "bold"),
        )
        text.tag_configure(
            "result", foreground=COL_INK,
            font=(MONO_FAMILY, 12, "bold"), spacing1=8, spacing3=8,
        )

        # Build content per metric
        builders = {
            "H":       self._calc_text_h,
            "L":       self._calc_text_l,
            "R":       self._calc_text_r,
            "eta":     self._calc_text_eta,
            "sigma2":  self._calc_text_sigma2,
            "sigma":   self._calc_text_sigma,
            "min_len": self._calc_text_min_len,
            "max_len": self._calc_text_max_len,
        }
        builder = builders.get(key)
        if builder:
            builder(text, m)
        else:
            text.insert(tk.END, "Sin contenido.\n", "body")

        text.configure(state="disabled")

        # Footer
        foot = tk.Frame(win, bg=COL_BG)
        foot.pack(fill=tk.X, padx=24, pady=(0, 20))

        RoundedButton(
            foot, text="Cerrar", command=win.destroy, bold=True,
            bg=COL_ACCENT, fg="#FFFFFF",
            hover_bg=COL_ACCENT_HOVER, active_bg=COL_ACCENT_ACTIVE,
            parent_bg=COL_BG, padx=22, pady=10,
        ).pack(side=tk.RIGHT)

        # Cierra con Esc; foco al modal (sin grab para no bloquear el scroll del padre)
        win.bind("<Escape>", lambda e: win.destroy())
        win.focus_set()

    # ---- builders por metrica ----

    @staticmethod
    def _format_byte(b: int) -> str:
        if 32 <= b < 127:
            return f"{b:3d} ({chr(b)!r})"
        return f"{b:3d}      "

    def _write_block(self, text: tk.Text, *, eyebrow: str | None = None,
                     formula: str | None = None) -> None:
        if eyebrow:
            text.insert(tk.END, eyebrow + "\n", "eyebrow")
        if formula:
            text.insert(tk.END, formula + "\n", "formula")

    def _calc_text_h(self, text: tk.Text, m: dict) -> None:
        freqs = self.current_freqs or {}
        total = m["total_symbols"]
        H = m["entropy"]

        self._write_block(
            text, eyebrow="FORMULA",
            formula="H  =  - Σ p(x) · log2( p(x) )",
        )
        text.insert(
            tk.END,
            "Donde p(x) = freq(x) / N, y N es el total de simbolos en la fuente.\n",
            "muted",
        )

        text.insert(tk.END, "\nDATOS\n", "eyebrow")
        text.insert(tk.END,
                    f"  N (total de bytes)        = {total:,}\n", "body")
        text.insert(tk.END,
                    f"  simbolos unicos           = {m['unique_symbols']:,}\n",
                    "body")

        text.insert(tk.END, "\nCONTRIBUCION POR SIMBOLO\n", "eyebrow")
        text.insert(
            tk.END,
            "  byte         freq        p(x)         -p · log2(p)\n", "muted",
        )
        text.insert(
            tk.END,
            "  ────         ────        ────         ────────────\n", "muted",
        )

        items = sorted(freqs.items(), key=lambda kv: -kv[1])
        shown_sum = 0.0
        max_show = 40
        for i, (b, f) in enumerate(items):
            if f <= 0:
                continue
            p = f / total
            contrib = -p * math.log2(p)
            shown_sum += contrib
            if i < max_show:
                text.insert(
                    tk.END,
                    f"  {self._format_byte(b)}  {f:8,}    {p:8.6f}    "
                    f"{contrib:12.6f}\n",
                    "body",
                )
        if len(items) > max_show:
            rest = len(items) - max_show
            text.insert(
                tk.END,
                f"  ... ({rest} simbolos mas)\n", "muted",
            )

        text.insert(tk.END, "\nSUMA\n", "eyebrow")
        text.insert(
            tk.END,
            f"  H = Σ contribuciones = {H:.6f} bits/simbolo\n", "accent",
        )

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  H = {H:.4f} bits / simbolo\n", "result")

    def _calc_text_l(self, text: tk.Text, m: dict) -> None:
        freqs = self.current_freqs or {}
        codes = self.current_codes or {}
        total = m["total_symbols"]
        L = m["mean_length"]

        self._write_block(
            text, eyebrow="FORMULA",
            formula="L  =  Σ p(x) · | codigo(x) |",
        )
        text.insert(
            tk.END,
            "Promedio ponderado de la longitud de codigo Huffman, "
            "usando p(x) como peso.\n",
            "muted",
        )

        text.insert(tk.END, "\nDATOS\n", "eyebrow")
        text.insert(tk.END, f"  N = {total:,}\n", "body")

        text.insert(tk.END, "\nCONTRIBUCION POR SIMBOLO\n", "eyebrow")
        text.insert(
            tk.END,
            "  byte         freq        p(x)        |c|     p · |c|\n", "muted",
        )
        text.insert(
            tk.END,
            "  ────         ────        ────        ───     ───────\n", "muted",
        )

        items = sorted(freqs.items(), key=lambda kv: -kv[1])
        max_show = 40
        for i, (b, f) in enumerate(items):
            p = f / total if total else 0.0
            cl = len(codes.get(b, ""))
            contrib = p * cl
            if i < max_show:
                text.insert(
                    tk.END,
                    f"  {self._format_byte(b)}  {f:8,}    {p:8.6f}    "
                    f"{cl:3d}     {contrib:8.6f}\n",
                    "body",
                )
        if len(items) > max_show:
            rest = len(items) - max_show
            text.insert(
                tk.END, f"  ... ({rest} simbolos mas)\n", "muted",
            )

        text.insert(tk.END, "\nSUMA\n", "eyebrow")
        text.insert(
            tk.END,
            f"  L = Σ p(x) · |codigo(x)| = {L:.6f} bits/simbolo\n",
            "accent",
        )

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  L = {L:.4f} bits / simbolo\n", "result")

    def _calc_text_r(self, text: tk.Text, m: dict) -> None:
        H = m["entropy"]
        L = m["mean_length"]
        R = m["redundancy"]

        self._write_block(
            text, eyebrow="FORMULA",
            formula="R  =  L  -  H",
        )
        text.insert(
            tk.END,
            "Cuantos bits/simbolo extra usa Huffman frente al optimo de Shannon.\n"
            "Por el teorema de Huffman, R esta entre 0 y menos de 1.\n",
            "muted",
        )

        text.insert(tk.END, "\nSUSTITUCION\n", "eyebrow")
        text.insert(tk.END, f"  L = {L:.6f}\n", "body")
        text.insert(tk.END, f"  H = {H:.6f}\n", "body")

        text.insert(tk.END, "\nOPERACION\n", "eyebrow")
        text.insert(
            tk.END, f"  R = L - H\n    = {L:.6f} - {H:.6f}\n",
            "body",
        )
        text.insert(tk.END, f"    = {R:.6f}\n", "accent")

        text.insert(tk.END, "\nINTERPRETACION\n", "eyebrow")
        if R < 0.05:
            interp = "Muy cerca del optimo: el codigo es casi tan eficiente como Shannon."
        elif R < 0.2:
            interp = "Ligera redundancia, normal en Huffman cuando las probabilidades no son potencias de 2."
        else:
            interp = "Redundancia notable: la fuente tiene probabilidades muy alejadas de potencias de 2."
        text.insert(tk.END, "  " + interp + "\n", "muted")

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  R = {R:.4f} bits / simbolo\n", "result")

    def _calc_text_eta(self, text: tk.Text, m: dict) -> None:
        H = m["entropy"]
        L = m["mean_length"]
        eta = m["efficiency"]

        self._write_block(
            text, eyebrow="FORMULA",
            formula="η  =  H / L",
        )
        text.insert(
            tk.END,
            "Fraccion del optimo teorico que el codigo Huffman esta alcanzando.\n"
            "Si vale 1 (100 %), el codigo es tan corto como Shannon permite.\n",
            "muted",
        )

        text.insert(tk.END, "\nSUSTITUCION\n", "eyebrow")
        text.insert(tk.END, f"  H = {H:.6f}\n", "body")
        text.insert(tk.END, f"  L = {L:.6f}\n", "body")

        text.insert(tk.END, "\nOPERACION\n", "eyebrow")
        text.insert(
            tk.END,
            f"  η = H / L\n    = {H:.6f} / {L:.6f}\n", "body",
        )
        text.insert(
            tk.END,
            f"    = {eta:.6f}\n    = {eta * 100:.4f} %\n", "accent",
        )

        text.insert(tk.END, "\nINTERPRETACION\n", "eyebrow")
        if eta >= 0.99:
            interp = "Excelente: practicamente igual al limite teorico."
        elif eta >= 0.95:
            interp = "Muy buena eficiencia."
        elif eta >= 0.90:
            interp = "Eficiencia aceptable; queda algo de margen."
        else:
            interp = "Eficiencia baja para Huffman; revisa la distribucion de simbolos."
        text.insert(tk.END, "  " + interp + "\n", "muted")

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  η = {eta * 100:.2f} %\n", "result")

    def _calc_text_sigma2(self, text: tk.Text, m: dict) -> None:
        freqs = self.current_freqs or {}
        codes = self.current_codes or {}
        total = m["total_symbols"]
        L = m["mean_length"]
        sigma2 = m["variance"]

        self._write_block(
            text, eyebrow="FORMULA",
            formula="σ²  =  Σ p(x) · ( | codigo(x) | - L )²",
        )
        text.insert(
            tk.END,
            "Dispersion ponderada de las longitudes de codigo respecto al promedio L.\n"
            "Una σ² alta significa codigos muy desiguales; baja, codigos uniformes.\n",
            "muted",
        )

        text.insert(tk.END, "\nDATOS\n", "eyebrow")
        text.insert(tk.END, f"  L (longitud media) = {L:.6f}\n", "body")
        text.insert(tk.END, f"  N (total bytes)    = {total:,}\n", "body")

        text.insert(tk.END, "\nCONTRIBUCION POR SIMBOLO\n", "eyebrow")
        text.insert(
            tk.END,
            "  byte         freq      p(x)       |c|    (|c|-L)²       p·(|c|-L)²\n",
            "muted",
        )
        text.insert(
            tk.END,
            "  ────         ────      ────       ───    ────────       ──────────\n",
            "muted",
        )

        items = sorted(freqs.items(), key=lambda kv: -kv[1])
        max_show = 40
        for i, (b, f) in enumerate(items):
            p = f / total if total else 0.0
            cl = len(codes.get(b, ""))
            diff_sq = (cl - L) ** 2
            contrib = p * diff_sq
            if i < max_show:
                text.insert(
                    tk.END,
                    f"  {self._format_byte(b)}  {f:8,}  {p:8.6f}   "
                    f"{cl:3d}    {diff_sq:9.4f}      {contrib:9.6f}\n",
                    "body",
                )
        if len(items) > max_show:
            rest = len(items) - max_show
            text.insert(
                tk.END, f"  ... ({rest} simbolos mas)\n", "muted",
            )

        text.insert(tk.END, "\nSUMA\n", "eyebrow")
        text.insert(
            tk.END,
            f"  σ² = Σ p(x) · (|c(x)| - L)² = {sigma2:.6f}\n", "accent",
        )

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  σ² = {sigma2:.4f} bits²\n", "result")

    def _calc_text_sigma(self, text: tk.Text, m: dict) -> None:
        sigma2 = m["variance"]
        sigma = m["std_dev"]

        self._write_block(
            text, eyebrow="FORMULA",
            formula="σ  =  √ σ²",
        )
        text.insert(
            tk.END,
            "Misma idea que la varianza, pero en bits, comparable directamente con L.\n",
            "muted",
        )

        text.insert(tk.END, "\nSUSTITUCION\n", "eyebrow")
        text.insert(tk.END, f"  σ² = {sigma2:.6f}\n", "body")

        text.insert(tk.END, "\nOPERACION\n", "eyebrow")
        text.insert(
            tk.END,
            f"  σ = √ σ²\n    = √ {sigma2:.6f}\n    = {sigma:.6f}\n",
            "accent",
        )

        text.insert(tk.END, "\nINTERPRETACION\n", "eyebrow")
        L = m["mean_length"]
        if L > 0:
            ratio = sigma / L
            if ratio < 0.1:
                tone = "Codigos muy uniformes."
            elif ratio < 0.3:
                tone = "Variacion moderada en las longitudes."
            else:
                tone = "Codigos bastante desiguales: hay simbolos muy frecuentes con codigos cortos y simbolos raros con codigos largos."
            text.insert(tk.END,
                        f"  σ / L = {ratio:.3f}  ·  {tone}\n", "muted")

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  σ = {sigma:.4f} bits\n", "result")

    def _calc_text_min_len(self, text: tk.Text, m: dict) -> None:
        codes = self.current_codes or {}
        freqs = self.current_freqs or {}
        if not codes:
            text.insert(tk.END, "Sin codigos.\n", "body")
            return
        min_len = m["min_code_len"]
        total = m["total_symbols"] or 1

        self._write_block(
            text, eyebrow="DEFINICION",
            formula="min |c|  =  min { longitud(codigo(x))  :  x ∈ fuente }",
        )
        text.insert(
            tk.END,
            "El codigo mas corto se asigna a los simbolos mas frecuentes "
            "(propiedad de Huffman).\n",
            "muted",
        )

        text.insert(tk.END, "\nVALOR\n", "eyebrow")
        text.insert(tk.END, f"  min |c| = {min_len} bits\n", "accent")

        winners = [
            (b, codes[b], freqs.get(b, 0))
            for b in codes if len(codes[b]) == min_len
        ]
        winners.sort(key=lambda t: -t[2])

        text.insert(
            tk.END,
            f"\nSIMBOLOS CON ESTA LONGITUD ({len(winners)})\n",
            "eyebrow",
        )
        text.insert(
            tk.END,
            "  byte         codigo                       freq      p(x)\n",
            "muted",
        )
        text.insert(
            tk.END,
            "  ────         ──────                       ────      ────\n",
            "muted",
        )
        for b, code, f in winners[:60]:
            p = f / total
            text.insert(
                tk.END,
                f"  {self._format_byte(b)}  {code:24s}    {f:7,}   {p:.6f}\n",
                "body",
            )
        if len(winners) > 60:
            text.insert(
                tk.END, f"  ... ({len(winners) - 60} mas)\n", "muted",
            )

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  min |c| = {min_len} bits\n", "result")

    def _calc_text_max_len(self, text: tk.Text, m: dict) -> None:
        codes = self.current_codes or {}
        freqs = self.current_freqs or {}
        if not codes:
            text.insert(tk.END, "Sin codigos.\n", "body")
            return
        max_len = m["max_code_len"]
        total = m["total_symbols"] or 1

        self._write_block(
            text, eyebrow="DEFINICION",
            formula="max |c|  =  max { longitud(codigo(x))  :  x ∈ fuente }",
        )
        text.insert(
            tk.END,
            "El codigo mas largo se asigna a los simbolos menos frecuentes.\n",
            "muted",
        )

        text.insert(tk.END, "\nVALOR\n", "eyebrow")
        text.insert(tk.END, f"  max |c| = {max_len} bits\n", "accent")

        winners = [
            (b, codes[b], freqs.get(b, 0))
            for b in codes if len(codes[b]) == max_len
        ]
        winners.sort(key=lambda t: t[2])

        text.insert(
            tk.END,
            f"\nSIMBOLOS CON ESTA LONGITUD ({len(winners)})\n",
            "eyebrow",
        )
        text.insert(
            tk.END,
            "  byte         codigo                            freq    p(x)\n",
            "muted",
        )
        text.insert(
            tk.END,
            "  ────         ──────                            ────    ────\n",
            "muted",
        )
        for b, code, f in winners[:60]:
            p = f / total
            text.insert(
                tk.END,
                f"  {self._format_byte(b)}  {code:30s}  {f:7,}   {p:.6f}\n",
                "body",
            )
        if len(winners) > 60:
            text.insert(
                tk.END, f"  ... ({len(winners) - 60} mas)\n", "muted",
            )

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  max |c| = {max_len} bits\n", "result")

    # ------------------------------------------------------------------
    # Modales del tab Resultado
    # ------------------------------------------------------------------

    _BITS_MODAL_LIMIT = 200_000

    _EFFICACY_TITLES = {
        "compression": ("Tasa de compresion", "T", "TASA DE COMPRESION"),
        "savings":     ("Ahorro de bits",     "A", "AHORRO"),
        "verification":("Verificacion de round-trip", "V", "VERIFICACION"),
    }

    def _modal_window(self, title: str, *, ww: int = 820, wh: int = 600,
                      min_w: int = 720, min_h: int = 520) -> tk.Toplevel:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=COL_BG)
        win.transient(self.root)
        win.minsize(min_w, min_h)

        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = max(self.root.winfo_width(), ww)
        rh = max(self.root.winfo_height(), wh)
        x = rx + (rw - ww) // 2
        y = ry + (rh - wh) // 2
        win.geometry(f"{ww}x{wh}+{max(0, x)}+{max(0, y)}")

        win.bind("<Escape>", lambda e: win.destroy())
        win.focus_set()
        return win

    def _modal_close_footer(self, win: tk.Toplevel) -> None:
        foot = tk.Frame(win, bg=COL_BG)
        foot.pack(fill=tk.X, padx=24, pady=(0, 20), side=tk.BOTTOM)
        RoundedButton(
            foot, text="Cerrar", command=win.destroy, bold=True,
            bg=COL_ACCENT, fg="#FFFFFF",
            hover_bg=COL_ACCENT_HOVER, active_bg=COL_ACCENT_ACTIVE,
            parent_bg=COL_BG, padx=22, pady=10,
        ).pack(side=tk.RIGHT)

    def _parse_encoded_meta(self) -> dict:
        """Lee encoded_text y devuelve original_size, bit_length, bits y JSON
        parseado. Devuelve dict vacio si no hay encoded_text valido."""
        if not self.encoded_text:
            return {}
        parts = self.encoded_text.split("\n", 2)
        if len(parts) < 2:
            return {}
        try:
            parsed = json.loads(parts[1])
        except Exception:
            parsed = {}
        bits = "".join((parts[2] if len(parts) > 2 else "").split())
        return {
            "original_size": int(parsed.get("original_size") or 0),
            "bit_length": int(parsed.get("bit_length") or 0) or len(bits),
            "frequencies": parsed.get("frequencies", {}) or {},
            "bits": bits,
            "version": parsed.get("version"),
        }

    # ---- Bits modal (vista expandida del bitstream) ----

    def _show_bits_modal(self) -> None:
        if not self.encoded_text:
            messagebox.showinfo(
                "Sin datos",
                "Codifica un archivo o pega texto codificado primero.",
            )
            return

        meta = self._parse_encoded_meta()
        bits = meta.get("bits", "")
        if not bits:
            messagebox.showinfo("Sin bits",
                                "El texto codificado no tiene bitstream.")
            return

        win = self._modal_window(
            "Secuencia de bits · vista expandida",
            ww=960, wh=680, min_w=820, min_h=540,
        )

        head = tk.Frame(win, bg=COL_BG)
        head.pack(fill=tk.X, padx=24, pady=(20, 6))
        ttk.Label(head, text="SECUENCIA DE BITS",
                  style="Eyebrow.TLabel").pack(anchor="w")
        title_row = tk.Frame(head, bg=COL_BG)
        title_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            title_row, text=f"{len(bits):,}",
            bg=COL_BG, fg=COL_INK, font=(FONT_FAMILY, 22, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            title_row, text="  bits del archivo codificado",
            bg=COL_BG, fg=COL_MUTED, font=(FONT_FAMILY, 12),
        ).pack(side=tk.LEFT, pady=(8, 0))

        actions = tk.Frame(win, bg=COL_BG)
        actions.pack(fill=tk.X, padx=24, pady=(8, 0))

        def copy_bits() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(bits)
            self.root.update()
            self._status(
                f"{len(bits):,} bits copiados al portapapeles.",
                color=COL_OK,
            )

        RoundedButton(
            actions, text="Copiar bits", command=copy_bits,
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT)

        tk.Frame(win, bg=COL_BORDER_SUBTLE, height=1).pack(
            fill=tk.X, padx=24, pady=(14, 0),
        )

        self._modal_close_footer(win)

        body = tk.Frame(win, bg=COL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=14)
        wrap = tk.Frame(body, bg=COL_BORDER, highlightthickness=0)
        wrap.pack(fill=tk.BOTH, expand=True)

        txt = scrolledtext.ScrolledText(
            wrap, wrap=tk.CHAR, font=(MONO_FAMILY, 12),
            bg=COL_SURFACE, fg=COL_INK,
            relief="flat", borderwidth=0, padx=20, pady=18,
            spacing1=2, spacing2=6, spacing3=2,
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        txt.tag_configure("note", foreground=COL_MUTED,
                          font=(FONT_FAMILY, 10))

        if len(bits) > self._BITS_MODAL_LIMIT:
            shown = self._format_bit_stream(
                bits[:self._BITS_MODAL_LIMIT], group=8, per_line=12,
            )
            txt.insert("1.0", shown + "\n\n")
            txt.insert(
                tk.END,
                f"... {len(bits) - self._BITS_MODAL_LIMIT:,} bits mas. "
                "Usa 'Guardar codificado' para el flujo completo.",
                "note",
            )
        else:
            txt.insert(
                "1.0",
                self._format_bit_stream(bits, group=8, per_line=12),
            )
        txt.configure(state="disabled")

    # ---- JSON modal (vista expandida de los metadatos) ----

    def _show_json_modal(self) -> None:
        if not self.encoded_text:
            messagebox.showinfo(
                "Sin datos",
                "Codifica un archivo o pega texto codificado primero.",
            )
            return

        meta = self._parse_encoded_meta()
        if not meta:
            messagebox.showinfo("Sin metadatos",
                                "El texto codificado no tiene JSON.")
            return

        try:
            payload = self.encoded_text.split("\n", 2)[1]
            parsed = json.loads(payload)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            pretty = self.encoded_text.split("\n", 2)[1] if self.encoded_text else ""
            parsed = {}

        win = self._modal_window(
            "Metadatos del codificado · vista expandida",
            ww=900, wh=660, min_w=720, min_h=520,
        )

        head = tk.Frame(win, bg=COL_BG)
        head.pack(fill=tk.X, padx=24, pady=(20, 6))
        ttk.Label(head, text="METADATOS DEL CODIFICADO",
                  style="Eyebrow.TLabel").pack(anchor="w")

        sym_row = tk.Frame(head, bg=COL_BG)
        sym_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            sym_row, text="JSON", bg=COL_BG, fg=COL_ACCENT,
            font=(FONT_FAMILY, 22, "bold"),
        ).pack(side=tk.LEFT)
        sub = (
            f"  {len(parsed.get('frequencies', {}))} simbolos  ·  "
            f"{int(parsed.get('bit_length', 0)):,} bits  ·  "
            f"{int(parsed.get('original_size', 0)):,} B originales"
        )
        tk.Label(
            sym_row, text=sub,
            bg=COL_BG, fg=COL_MUTED, font=(FONT_FAMILY, 11),
        ).pack(side=tk.LEFT, pady=(8, 0))

        actions = tk.Frame(win, bg=COL_BG)
        actions.pack(fill=tk.X, padx=24, pady=(8, 0))

        def copy_json() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(pretty)
            self.root.update()
            self._status("Metadatos copiados al portapapeles.", color=COL_OK)

        RoundedButton(
            actions, text="Copiar JSON", command=copy_json,
            bg=COL_RAISED, fg=COL_INK,
            hover_bg=COL_BORDER_SUBTLE, active_bg=COL_BORDER,
            parent_bg=COL_BG, padx=14, pady=8,
        ).pack(side=tk.LEFT)

        tk.Frame(win, bg=COL_BORDER_SUBTLE, height=1).pack(
            fill=tk.X, padx=24, pady=(14, 0),
        )

        self._modal_close_footer(win)

        body = tk.Frame(win, bg=COL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=14)
        wrap = tk.Frame(body, bg=COL_BORDER, highlightthickness=0)
        wrap.pack(fill=tk.BOTH, expand=True)

        txt = scrolledtext.ScrolledText(
            wrap, wrap=tk.WORD, font=(MONO_FAMILY, 11),
            bg=COL_SURFACE, fg=COL_INK,
            relief="flat", borderwidth=0, padx=20, pady=18,
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        txt.insert("1.0", pretty)
        txt.configure(state="disabled")

    # ---- Efficacy modals (TASA, AHORRO, VERIFICACION) ----

    def _show_efficacy_modal(self, key: str) -> None:
        if not self.encoded_text:
            messagebox.showinfo(
                "Sin datos",
                "Codifica un archivo para ver las metricas de eficacia.",
            )
            return

        title, symbol, eyebrow_text = self._EFFICACY_TITLES.get(
            key, (key, key, key.upper()),
        )

        win = self._modal_window(
            f"Calculo · {title}",
            ww=820, wh=620, min_w=720, min_h=540,
        )

        head = tk.Frame(win, bg=COL_BG)
        head.pack(fill=tk.X, padx=24, pady=(20, 8))
        ttk.Label(head, text=eyebrow_text,
                  style="Eyebrow.TLabel").pack(anchor="w")
        sym_row = tk.Frame(head, bg=COL_BG)
        sym_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            sym_row, text=symbol, bg=COL_BG, fg=COL_ACCENT,
            font=(FONT_FAMILY, 22, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            sym_row, text=f"  {title}", bg=COL_BG, fg=COL_INK,
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(side=tk.LEFT)

        tk.Frame(win, bg=COL_BORDER_SUBTLE, height=1).pack(
            fill=tk.X, padx=24, pady=(12, 0),
        )

        self._modal_close_footer(win)

        body_wrap = tk.Frame(win, bg=COL_BG)
        body_wrap.pack(fill=tk.BOTH, expand=True, padx=24, pady=(14, 12))

        text = scrolledtext.ScrolledText(
            body_wrap, wrap=tk.WORD, font=(MONO_FAMILY, 10),
            bg=COL_SURFACE, fg=COL_INK,
            relief="flat", borderwidth=0, padx=18, pady=16,
            highlightthickness=1, highlightbackground=COL_BORDER,
        )
        text.pack(fill=tk.BOTH, expand=True)

        text.tag_configure("eyebrow", foreground=COL_MUTED,
                           font=(FONT_FAMILY, 8, "bold"),
                           spacing1=10, spacing3=4)
        text.tag_configure("formula", foreground=COL_ACCENT,
                           font=(MONO_FAMILY, 11, "bold"),
                           spacing1=4, spacing3=8)
        text.tag_configure("body", foreground=COL_INK,
                           font=(MONO_FAMILY, 10))
        text.tag_configure("muted", foreground=COL_MUTED,
                           font=(MONO_FAMILY, 9))
        text.tag_configure("accent", foreground=COL_ACCENT,
                           font=(MONO_FAMILY, 10, "bold"))
        text.tag_configure("result", foreground=COL_INK,
                           font=(MONO_FAMILY, 12, "bold"),
                           spacing1=8, spacing3=8)
        text.tag_configure("ok", foreground=COL_OK,
                           font=(MONO_FAMILY, 10, "bold"))
        text.tag_configure("warn", foreground=COL_WARN,
                           font=(MONO_FAMILY, 10, "bold"))

        builders = {
            "compression":  self._calc_text_compression,
            "savings":      self._calc_text_savings,
            "verification": self._calc_text_verification,
        }
        builder = builders.get(key)
        if builder:
            builder(text, self._parse_encoded_meta())
        text.configure(state="disabled")

    def _calc_text_compression(self, text: tk.Text, meta: dict) -> None:
        bits = meta.get("bit_length", 0)
        bytes_orig = meta.get("original_size", 0)
        bits_orig = bytes_orig * 8

        text.insert(tk.END, "QUE MIDE\n", "eyebrow")
        text.insert(
            tk.END,
            "Que fraccion del archivo original ocupa el bitstream\n"
            "codificado, medido en bits.\n",
            "muted",
        )

        self._write_block(
            text, eyebrow="FORMULA",
            formula="T  =  bits_codificados / (bytes_originales × 8) × 100",
        )

        text.insert(tk.END, "\nDATOS\n", "eyebrow")
        text.insert(tk.END, f"  bits codificados   = {bits:,}\n", "body")
        text.insert(tk.END, f"  bytes originales   = {bytes_orig:,}\n", "body")
        text.insert(
            tk.END,
            f"  bits originales    = {bytes_orig:,} × 8 = {bits_orig:,}\n",
            "body",
        )

        if bits_orig <= 0:
            text.insert(tk.END,
                        "\n  Sin datos suficientes para calcular.\n",
                        "muted")
            return

        rate = bits / bits_orig * 100
        text.insert(tk.END, "\nOPERACION\n", "eyebrow")
        text.insert(
            tk.END,
            f"  T = {bits:,} / {bits_orig:,} × 100\n", "body",
        )
        text.insert(tk.END, f"    = {rate:.4f} %\n", "accent")

        text.insert(tk.END, "\nINTERPRETACION\n", "eyebrow")
        if rate >= 100:
            interp = ("El codificado ocupa lo mismo o mas que el original. "
                      "Sin compresion real.")
        elif rate >= 75:
            interp = "Compresion modesta. La fuente tiene poca redundancia."
        elif rate >= 50:
            interp = ("Compresion clara. El archivo bajo a la mitad o "
                      "tres cuartos de bits.")
        else:
            interp = ("Compresion fuerte. La fuente es muy redundante o "
                      "muy sesgada hacia pocos simbolos.")
        text.insert(tk.END, "  " + interp + "\n", "muted")

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(tk.END, f"  T = {rate:.2f} %\n", "result")

    def _calc_text_savings(self, text: tk.Text, meta: dict) -> None:
        bits = meta.get("bit_length", 0)
        bytes_orig = meta.get("original_size", 0)
        bits_orig = bytes_orig * 8

        text.insert(tk.END, "QUE MIDE\n", "eyebrow")
        text.insert(
            tk.END,
            "El complemento de la tasa: cuantos bits del original\n"
            "desaparecieron al codificar.\n",
            "muted",
        )

        self._write_block(
            text, eyebrow="FORMULA",
            formula="A  =  100 %  -  T",
        )

        if bits_orig <= 0:
            text.insert(tk.END,
                        "\n  Sin datos suficientes para calcular.\n",
                        "muted")
            return

        rate = bits / bits_orig * 100
        savings = max(0.0, 100 - rate)
        bits_saved = bits_orig - bits

        text.insert(tk.END, "\nDATOS\n", "eyebrow")
        text.insert(tk.END, f"  T (tasa)           = {rate:.4f} %\n", "body")

        text.insert(tk.END, "\nOPERACION\n", "eyebrow")
        text.insert(tk.END, f"  A = 100 - {rate:.4f}\n", "body")
        text.insert(tk.END, f"    = {savings:.4f} %\n", "accent")

        text.insert(tk.END, "\nEQUIVALENCIA EN BITS\n", "eyebrow")
        text.insert(
            tk.END,
            f"  bits ahorrados = bits_orig - bits_cod\n"
            f"                 = {bits_orig:,} - {bits:,}\n",
            "body",
        )
        text.insert(tk.END, f"                 = {bits_saved:,} bits\n",
                    "accent")

        text.insert(tk.END, "\nINTERPRETACION\n", "eyebrow")
        text.insert(
            tk.END,
            "  Mas alto = mejor compresion. El A es la cara visible\n"
            "  del logro: 'me ahorre Y % de bits'.\n",
            "muted",
        )

        text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
        text.insert(
            tk.END,
            f"  A = {savings:.2f} %  ({bits_saved:,} bits eliminados)\n",
            "result",
        )

    def _calc_text_verification(self, text: tk.Text, meta: dict) -> None:
        expected = meta.get("original_size", 0)

        text.insert(tk.END, "QUE COMPRUEBA\n", "eyebrow")
        text.insert(
            tk.END,
            "Que decodificar el bitstream reconstruye exactamente\n"
            "los bytes del archivo original. El round-trip de Huffman\n"
            "es lossless por construccion: aqui se confirma con datos.\n",
            "muted",
        )

        self._write_block(
            text, eyebrow="COMO",
            formula="V  =  len(decoded_bytes) / original_size × 100",
        )

        text.insert(tk.END, "\nESTADO ACTUAL\n", "eyebrow")
        if self.decoded_bytes is None:
            text.insert(
                tk.END,
                "  Sin decodificar todavia. Pulsa 'Decodificar'\n"
                "  para verificar el round-trip.\n",
                "muted",
            )
            text.insert(tk.END,
                        f"\n  bytes esperados    = {expected:,}\n", "body")
            text.insert(tk.END,
                        "  bytes obtenidos    = pendiente\n", "body")
        else:
            got = len(self.decoded_bytes)
            text.insert(tk.END,
                        f"  bytes esperados    = {expected:,}\n", "body")
            text.insert(tk.END,
                        f"  bytes obtenidos    = {got:,}\n", "body")
            if expected and got == expected:
                text.insert(
                    tk.END,
                    "\n  Round-trip OK: todos los bytes coinciden.\n",
                    "ok",
                )
                text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
                text.insert(tk.END, "  V = 100.00 %  ✓\n", "result")
            elif expected:
                pct = got / expected * 100
                text.insert(
                    tk.END,
                    f"\n  MISMATCH: {got - expected:+d} bytes "
                    "respecto al esperado.\n",
                    "warn",
                )
                text.insert(tk.END, "\nRESULTADO\n", "eyebrow")
                text.insert(tk.END, f"  V = {pct:.2f} %\n", "result")
            else:
                text.insert(tk.END,
                            "\n  Sin tamano de referencia en el JSON.\n",
                            "muted")

        text.insert(tk.END, "\nPOR QUE IMPORTA\n", "eyebrow")
        text.insert(
            tk.END,
            "Huffman es lossless por construccion: la codificacion es\n"
            "una sustitucion biyectiva entre simbolos y prefijos. Si\n"
            "esta verificacion baja del 100 %, hay corrupcion en el\n"
            ".txt (caracteres no binarios, bits cortados, JSON roto)\n"
            "o un bug en el decoder. No deberia pasar nunca con un\n"
            "archivo intacto.\n",
            "muted",
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def load_media(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in MEDIA_EXTENSIONS.split())
        path = filedialog.askopenfilename(
            title="Selecciona archivo a codificar",
            filetypes=[("Archivos compatibles", patterns), ("Todos", "*.*")],
        )
        if not path:
            return
        p = Path(path)
        try:
            data = p.read_bytes()
        except OSError as e:
            messagebox.showerror("Error al leer", str(e))
            return
        self.loaded_bytes = data
        self.loaded_path = p
        self.encoded_source_path = None
        self.encoded_text = None
        self.decoded_bytes = None
        self.info_var.set(
            f"{p.name}  ·  {len(data):,} bytes  ·  {p.suffix or 'sin extension'}"
        )
        self.log_text.delete("1.0", tk.END)
        self._clear_output_panels()
        self._reset_steps()
        self.current_root = None
        self.current_codes = None
        self.current_freqs = None
        self.current_metrics = None
        self.last_action_label = f"Original cargado · {p.name}"
        self._draw_tree_placeholder()
        self._update_metrics(input=f"{len(data):,} B", symbols=EMPTY_VALUE,
                             bits=EMPTY_VALUE, output=EMPTY_VALUE,
                             ratio=EMPTY_VALUE)
        self.log(f"Archivo cargado: {p}")
        self.log(f"Tamano: {len(data)} bytes")
        self._set_preview(data)
        self._refresh_analysis()
        self._status(f"'{p.name}' cargado. Pulsa 'Codificar'.", color=COL_OK)

    def do_encode(self) -> None:
        if not self.loaded_bytes:
            messagebox.showwarning(
                "Falta archivo",
                "Primero carga una imagen o audio.",
            )
            return
        self.log_text.delete("1.0", tk.END)
        self._clear_output_panels()
        self._reset_steps()
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            text = encode(self.loaded_bytes, log=self.log,
                          on_tree=self._capture_tree)
        except Exception as e:
            messagebox.showerror("Error codificando", str(e))
            self._status("Error en la codificacion.", color=COL_WARN)
            return
        finally:
            self.root.config(cursor="")
        self.encoded_text = text
        self._set_output(text)

        n_in = len(self.loaded_bytes)
        n_out = len(text)
        n_sym = len(self.current_freqs or {})
        bits_total = sum(
            len(self.current_codes[b]) * f
            for b, f in (self.current_freqs or {}).items()
        )
        ratio = bits_total / (n_in * 8) * 100 if n_in else 0
        self._update_metrics(
            input=f"{n_in:,} B",
            symbols=str(n_sym),
            bits=f"{bits_total:,}",
            output=f"{n_out:,} ch",
            ratio=f"{ratio:.1f} %",
        )

        # Calcular metricas de teoria de la informacion
        self.current_metrics = _calculate_metrics(
            self.current_freqs or {}, self.current_codes or {},
        )
        name = self.loaded_path.name if self.loaded_path else "datos"
        self.last_action_label = f"Codificacion · {name}"
        self._refresh_analysis()

        self._status(
            f"Codificado: {n_out:,} caracteres. Mira 'Analisis' y 'Arbol'.",
            color=COL_OK,
        )

    def load_encoded(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona .txt codificado",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Error al leer", str(e))
            return
        self.encoded_text = text
        self.encoded_source_path = Path(path)
        self.loaded_path = None
        self.loaded_bytes = None
        self.decoded_bytes = None
        self._set_output(text)
        self.info_var.set(
            f"{Path(path).name}  ·  {len(text):,} caracteres codificados"
        )
        self._set_preview(None)
        self.current_metrics = None
        self._refresh_analysis()
        self._status("Texto codificado cargado. Pulsa 'Decodificar'.",
                     color=COL_OK)

    def do_decode(self) -> None:
        text = (self.encoded_text or "").strip()
        if not text:
            messagebox.showwarning(
                "Nada que decodificar",
                "Carga un .txt codificado o pulsa "
                "'Pegar texto crudo' en la pestana Resultado.",
            )
            return
        self.log_text.delete("1.0", tk.END)
        self._reset_steps()
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            data = decode(text, log=self.log, on_tree=self._capture_tree)
        except Exception as e:
            messagebox.showerror("Error decodificando", str(e))
            self._status("Error en la decodificacion.", color=COL_WARN)
            return
        finally:
            self.root.config(cursor="")
        self.decoded_bytes = data
        self._update_verification()
        self._set_preview(data)
        self._update_metrics(
            input=f"{len(text):,} ch",
            symbols=str(len(self.current_freqs or {})),
            bits=EMPTY_VALUE,
            output=f"{len(data):,} B",
            ratio=EMPTY_VALUE,
        )

        self.current_metrics = _calculate_metrics(
            self.current_freqs or {}, self.current_codes or {},
        )
        self.last_action_label = "Decodificacion · datos reconstruidos"
        self._refresh_analysis()

        self._status(
            f"Decodificado: {len(data):,} bytes reconstruidos.",
            color=COL_OK,
        )
        messagebox.showinfo(
            "Decodificacion lista",
            f"Se reconstruyeron {len(data)} bytes. "
            "Guardalos con 'Restaurar media'.",
        )

    def save_encoded(self) -> None:
        if not self.encoded_text:
            messagebox.showwarning(
                "Nada que guardar",
                "Primero codifica un archivo.",
            )
            return
        if self.loaded_path is not None:
            default = f"coded-{self.loaded_path.stem}.txt"
        else:
            default = "coded-media.txt"
        path = filedialog.asksaveasfilename(
            title="Guardar resultado codificado",
            defaultextension=".txt",
            initialfile=default,
            filetypes=[("Texto", "*.txt")],
        )
        if not path:
            return
        try:
            Path(path).write_text(self.encoded_text, encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Error al guardar", str(e))
            return
        self._status(f"Guardado: {path}", color=COL_OK)
        messagebox.showinfo("Guardado", f"Archivo guardado en:\n{path}")

    @staticmethod
    def _sniff_extension(data: bytes) -> str:
        """Inspecciona magic bytes y devuelve la extension probable.

        Cobertura: imagen comun (png/jpg/gif/bmp/webp/tiff), audio
        (wav/mp3/flac/ogg/m4a), video (mp4/webm), texto/PDF. Devuelve
        cadena vacia si no reconoce el formato.
        """
        if not data:
            return ""
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return ".gif"
        if data.startswith(b"BM"):
            return ".bmp"
        if data.startswith(b"RIFF") and len(data) >= 12:
            container = data[8:12]
            if container == b"WAVE":
                return ".wav"
            if container == b"WEBP":
                return ".webp"
            if container == b"AVI ":
                return ".avi"
        if data.startswith(b"ID3") or data[:2] == b"\xff\xfb":
            return ".mp3"
        if data.startswith(b"fLaC"):
            return ".flac"
        if data.startswith(b"OggS"):
            return ".ogg"
        if data[:4] in (b"II*\x00", b"MM\x00*"):
            return ".tif"
        if data.startswith(b"%PDF-"):
            return ".pdf"
        if len(data) >= 12 and data[4:8] == b"ftyp":
            brand = data[8:12]
            if brand in (b"isom", b"mp42", b"avc1", b"mp41",
                         b"iso2", b"M4V "):
                return ".mp4"
            if brand in (b"M4A ", b"M4B "):
                return ".m4a"
        if len(data) >= 4 and data[:4] == b"\x1aE\xdf\xa3":
            return ".webm"
        # Texto plano: si todos los bytes son ASCII imprimibles + espacios
        sample = data[:512]
        if sample and all(b == 9 or b == 10 or b == 13 or 32 <= b < 127
                          for b in sample):
            return ".txt"
        return ""

    @staticmethod
    def _suggest_decoded_name(loaded_path,
                              encoded_source_path,
                              decoded_bytes: bytes | None) -> tuple[str, str]:
        """Devuelve (nombre_por_defecto, extension) para 'Restaurar media'.

        Prioridad:
          1. loaded_path: usa stem y suffix (caso estandar).
          2. encoded_source_path 'coded-xyz.txt': recupera stem 'xyz', y la
             extension se olfatea de los bytes decodificados.
          3. Generico 'media' + olfateo de extension.
        """
        if loaded_path is not None:
            stem = loaded_path.stem
            ext = loaded_path.suffix
        else:
            if encoded_source_path is not None:
                enc_stem = encoded_source_path.stem
                if enc_stem.startswith("coded-"):
                    stem = enc_stem[len("coded-"):] or "media"
                else:
                    stem = enc_stem
            else:
                stem = "media"
            ext = App._sniff_extension(decoded_bytes or b"")
        return f"restored-{stem}{ext}", ext

    def save_decoded(self) -> None:
        if self.decoded_bytes is None:
            messagebox.showwarning(
                "Nada que guardar",
                "Primero decodifica un texto codificado.",
            )
            return

        default, ext = self._suggest_decoded_name(
            self.loaded_path,
            self.encoded_source_path,
            self.decoded_bytes,
        )

        if ext:
            ext_label = ext.lstrip(".").upper()
            filetypes = [
                (f"{ext_label} ({ext})", f"*{ext}"),
                ("Todos", "*.*"),
            ]
        else:
            filetypes = [("Todos", "*.*")]

        path = filedialog.asksaveasfilename(
            title="Guardar media decodificada",
            defaultextension=ext or "",
            initialfile=default,
            filetypes=filetypes,
        )
        if not path:
            return
        try:
            Path(path).write_bytes(self.decoded_bytes)
        except OSError as e:
            messagebox.showerror("Error al guardar", str(e))
            return
        self._status(f"Media decodificada guardada: {path}", color=COL_OK)
        messagebox.showinfo("Guardado", f"Archivo guardado en:\n{path}")

    def copy_output(self) -> None:
        if not self.encoded_text:
            messagebox.showwarning(
                "Nada que copiar",
                "Primero codifica un archivo.",
            )
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.encoded_text)
        self.root.update()
        self._status(
            f"Copiado al portapapeles ({len(self.encoded_text):,} caracteres).",
            color=COL_OK,
        )

    def clear(self) -> None:
        self.loaded_bytes = None
        self.loaded_path = None
        self.encoded_source_path = None
        self.encoded_text = None
        self.decoded_bytes = None
        self.current_root = None
        self.current_codes = None
        self.current_freqs = None
        self.current_metrics = None
        self.last_action_label = "sin operacion"
        self.log_text.delete("1.0", tk.END)
        self._clear_output_panels()
        self.info_var.set("Sin archivo cargado.")
        self._reset_steps()
        self._update_metrics(input=EMPTY_VALUE, symbols=EMPTY_VALUE,
                             bits=EMPTY_VALUE, output=EMPTY_VALUE,
                             ratio=EMPTY_VALUE)
        self._draw_tree_placeholder()
        self._set_preview(None)
        self._refresh_analysis()
        self._status("Listo.", color=COL_OK)


def main() -> None:
    global FONT_FAMILY, MONO_FAMILY
    root = tk.Tk()
    FONT_FAMILY = _pick_font()
    MONO_FAMILY = _pick_mono()
    try:
        default = tkfont.nametofont("TkDefaultFont")
        default.configure(family=FONT_FAMILY, size=10)
        for name in ("TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=FONT_FAMILY)
            except tk.TclError:
                pass
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
