"""Interfaz Tkinter minimalista para codificar/decodificar con Huffman."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, scrolledtext, ttk

from huffman import ALGORITHM_NAME, Node, decode, encode


def _pick_font() -> str:
    try:
        families = set(tkfont.families())
    except tk.TclError:
        return "Segoe UI"
    for name in ("Montserrat", "Roboto", "Segoe UI", "Helvetica"):
        if name in families:
            return name
    return "TkDefaultFont"


FONT_FAMILY = "Segoe UI"  # se reemplaza tras crear root

MEDIA_EXTENSIONS = ".png .jpg .jpeg .gif .bmp .tiff .webp .wav .mp3 .ogg .flac .m4a .aac"
DISPLAY_LIMIT = 60_000

# Paleta gris minimalista
COL_BG = "#f5f5f5"
COL_PANEL = "#ffffff"
COL_BORDER = "#d4d4d4"
COL_TEXT = "#2b2b2b"
COL_MUTED = "#707070"
COL_ACCENT = "#3a3a3a"
COL_SOFT = "#ececec"
COL_LEAF = "#4a4a4a"
COL_INNER = "#9a9a9a"
COL_EDGE = "#777777"
COL_OK = "#2e7d32"
COL_BTN = "#e8e8e8"
COL_BTN_HOVER = "#dcdcdc"
COL_BTN_ACTIVE = "#cfcfcf"
COL_ACCENT_HOVER = "#505050"


class RoundedButton(tk.Canvas):
    """Boton plano con esquinas redondeadas dibujado en Canvas."""

    def __init__(self, parent, text: str, command=None, *,
                 bg: str = COL_BTN, fg: str = COL_TEXT,
                 hover_bg: str | None = None, active_bg: str | None = None,
                 font=None, padx: int = 14, pady: int = 8, radius: int = 4,
                 parent_bg: str = COL_BG, bold: bool = False) -> None:
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0)
        self.command = command
        self.bg = bg
        self.fg = fg
        self.hover_bg = hover_bg or bg
        self.active_bg = active_bg or hover_bg or bg
        self.radius = radius
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

    def _round_rect(self, color: str) -> None:
        r = self.radius
        w, h = self.w, self.h
        pts = [
            r, 0, w - r, 0, w, 0, w, r,
            w, h - r, w, h, w - r, h,
            r, h, 0, h, 0, h - r,
            0, r, 0, 0, r, 0,
        ]
        self.create_polygon(pts, smooth=True, splinesteps=12,
                            fill=color, outline=color)

    def _draw(self, color: str) -> None:
        self._current = color
        self.delete("all")
        self._round_rect(color)
        self.create_text(self.w / 2, self.h / 2, text=self.text,
                         fill=self.fg, font=self.font)

    def _on_release(self, event) -> None:
        self._draw(self.hover_bg)
        if (0 <= event.x <= self.w) and (0 <= event.y <= self.h):
            if self.command:
                self.command()


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Milloxcoder — Huffman Encoder / Decoder")
        self.root.configure(bg=COL_BG)
        self.root.minsize(980, 640)
        self.root.resizable(True, True)
        self._center_window(1320, 860)

        self.loaded_bytes: bytes | None = None
        self.loaded_path: Path | None = None
        self.encoded_text: str | None = None
        self.decoded_bytes: bytes | None = None
        self.current_root: Node | None = None
        self.current_codes: dict | None = None
        self.current_freqs: dict | None = None

        self._configure_style()
        self._build_ui()

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Respeta la barra de tareas usando el area de trabajo disponible en Windows
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

    # ---------------- estilos ----------------

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        f = FONT_FAMILY
        style.configure(".", background=COL_BG, foreground=COL_TEXT, font=(f, 10))
        style.configure("TFrame", background=COL_BG)
        style.configure("Card.TFrame", background=COL_PANEL, relief="flat")
        style.configure("TLabel", background=COL_BG, foreground=COL_TEXT, font=(f, 10))
        style.configure("Muted.TLabel", background=COL_BG, foreground=COL_MUTED, font=(f, 9))
        style.configure("Header.TLabel", background=COL_BG, foreground=COL_TEXT,
                        font=(f, 17, "bold"))
        style.configure("Sub.TLabel", background=COL_BG, foreground=COL_MUTED,
                        font=(f, 9))
        style.configure("Info.TLabel", background=COL_SOFT, foreground=COL_TEXT,
                        padding=10, font=(f, 9))
        style.configure("Status.TLabel", background="#e5e5e5", foreground=COL_MUTED,
                        padding=6, font=(f, 9))

        # Tabs de tamano fijo (sin expansion al seleccionar)
        style.layout("TNotebook.Tab", [
            ("Notebook.tab", {"sticky": "nswe", "children": [
                ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                    ("Notebook.label", {"side": "top", "sticky": ""}),
                ]}),
            ]}),
        ])
        style.configure("TNotebook", background=COL_BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
        style.configure("TNotebook.Tab",
                        background="#e5e5e5", foreground=COL_MUTED,
                        padding=(22, 10), borderwidth=0, font=(f, 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", COL_ACCENT), ("active", "#dcdcdc")],
                  foreground=[("selected", "#ffffff"), ("active", COL_TEXT)],
                  padding=[("selected", (22, 10)), ("!selected", (22, 10))],
                  expand=[("selected", [0, 0, 0, 0])])

        style.configure("TLabelframe", background=COL_BG, foreground=COL_MUTED,
                        borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=COL_BG, foreground=COL_MUTED,
                        font=(f, 9, "bold"))

        # Scrollbar delgado en gris
        style.configure("Vertical.TScrollbar", background=COL_SOFT,
                        troughcolor=COL_BG, borderwidth=0, arrowcolor=COL_MUTED)
        style.configure("Horizontal.TScrollbar", background=COL_SOFT,
                        troughcolor=COL_BG, borderwidth=0, arrowcolor=COL_MUTED)

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="TFrame")
        outer.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        # Cabecera
        head = ttk.Frame(outer, style="TFrame")
        head.pack(fill=tk.X)
        ttk.Label(head, text="Milloxcoder", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            head,
            text=f"{ALGORITHM_NAME} · compresion sin perdida de imagen y audio",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        # Barra de acciones
        actions = ttk.Frame(outer, style="TFrame")
        actions.pack(fill=tk.X, pady=(0, 10))

        primary = [
            ("Cargar archivo", self.load_media),
            ("Codificar", self.do_encode),
            ("Decodificar", self.do_decode),
        ]
        secondary = [
            ("Cargar .txt codificado", self.load_encoded),
            ("Guardar .txt", self.save_encoded),
            ("Guardar media", self.save_decoded),
            ("Copiar", self.copy_output),
            ("Limpiar", self.clear),
        ]
        for label, cmd in primary:
            RoundedButton(
                actions, text=label, command=cmd, bold=True,
                bg=COL_ACCENT, fg="#ffffff",
                hover_bg=COL_ACCENT_HOVER, active_bg="#222222",
                parent_bg=COL_BG,
            ).pack(side=tk.LEFT, padx=(0, 6))
        sep = tk.Frame(actions, bg=COL_BORDER, width=1, height=28)
        sep.pack(side=tk.LEFT, padx=8, pady=4)
        for label, cmd in secondary:
            RoundedButton(
                actions, text=label, command=cmd,
                bg=COL_BTN, fg=COL_TEXT,
                hover_bg=COL_BTN_HOVER, active_bg=COL_BTN_ACTIVE,
                parent_bg=COL_BG,
            ).pack(side=tk.LEFT, padx=3)

        # Info archivo
        self.info_var = tk.StringVar(value="Sin archivo cargado.")
        ttk.Label(outer, textvariable=self.info_var, style="Info.TLabel").pack(fill=tk.X, pady=(0, 10))

        # Notebook con pestañas
        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True)

        self._build_process_tab(nb)
        self._build_tree_tab(nb)
        self._build_output_tab(nb)

        # Barra de estado
        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(outer, textvariable=self.status_var, style="Status.TLabel").pack(fill=tk.X, pady=(10, 0))

    def _build_process_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, style="Card.TFrame", padding=10)
        nb.add(frame, text="  Proceso  ")

        # Indicador de pasos
        self.steps_frame = ttk.Frame(frame, style="Card.TFrame")
        self.steps_frame.pack(fill=tk.X, pady=(0, 10))
        self.step_labels: list[tk.Label] = []
        steps = ["1 · Leer", "2 · Frecuencias", "3 · Arbol", "4 · Codigos",
                 "5 · Bits", "6 · Serializar"]
        for i, txt in enumerate(steps):
            lbl = tk.Label(self.steps_frame, text=txt, font=(FONT_FAMILY, 9),
                           bg="#e8e8e8", fg=COL_MUTED, padx=10, pady=5)
            lbl.pack(side=tk.LEFT, padx=(0, 4))
            self.step_labels.append(lbl)

        # Metricas
        metrics = ttk.Frame(frame, style="Card.TFrame")
        metrics.pack(fill=tk.X, pady=(0, 10))
        self.metric_vars = {
            "input": tk.StringVar(value="—"),
            "symbols": tk.StringVar(value="—"),
            "bits": tk.StringVar(value="—"),
            "output": tk.StringVar(value="—"),
            "ratio": tk.StringVar(value="—"),
        }
        titles = [("Entrada", "input"), ("Simbolos", "symbols"),
                  ("Bits generados", "bits"), ("Salida", "output"), ("Ratio", "ratio")]
        for i, (title, key) in enumerate(titles):
            card = tk.Frame(metrics, bg=COL_SOFT, padx=14, pady=8)
            card.grid(row=0, column=i, sticky="ew", padx=(0, 6))
            metrics.columnconfigure(i, weight=1)
            tk.Label(card, text=title, bg=COL_SOFT, fg=COL_MUTED,
                     font=(FONT_FAMILY, 8)).pack(anchor="w")
            tk.Label(card, textvariable=self.metric_vars[key], bg=COL_SOFT, fg=COL_TEXT,
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")

        # Log
        log_label = ttk.Label(frame, text="Registro paso a paso", style="Sub.TLabel")
        log_label.pack(anchor="w", pady=(4, 4))
        log_container = tk.Frame(frame, bg=COL_BORDER, bd=1)
        log_container.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(
            log_container, wrap=tk.WORD, font=("Consolas", 9),
            bg="#fafafa", fg=COL_TEXT, relief="flat", borderwidth=0, padx=10, pady=8,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Tags de color para el log
        self.log_text.tag_configure("step", foreground="#1a1a1a",
                                    font=("Consolas", 10, "bold"), spacing1=6, spacing3=3)
        self.log_text.tag_configure("sub", foreground=COL_MUTED)
        self.log_text.tag_configure("ok", foreground=COL_OK,
                                    font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("warn", foreground="#c77700")

    def _build_tree_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, style="Card.TFrame", padding=10)
        nb.add(frame, text="  Arbol de Huffman  ")

        top = ttk.Frame(frame, style="Card.TFrame")
        top.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(top, text="Arbol generado durante la (de)codificacion",
                  style="Sub.TLabel").pack(side=tk.LEFT)

        RoundedButton(top, text="Exportar imagen", command=self._export_tree,
                      parent_bg=COL_BG).pack(side=tk.RIGHT, padx=(6, 0))
        RoundedButton(top, text="Centrar", command=self._center_tree,
                      parent_bg=COL_BG).pack(side=tk.RIGHT, padx=(6, 0))
        RoundedButton(top, text="Ajustar", command=self._redraw_tree,
                      parent_bg=COL_BG).pack(side=tk.RIGHT, padx=(6, 0))

        legend = tk.Frame(top, bg=COL_BG)
        legend.pack(side=tk.RIGHT, padx=12)
        for col, txt in [(COL_LEAF, "hoja (byte)"), (COL_INNER, "nodo interno")]:
            sw = tk.Frame(legend, bg=col, width=12, height=12)
            sw.pack(side=tk.LEFT, padx=(6, 4))
            tk.Label(legend, text=txt, bg=COL_BG, fg=COL_MUTED,
                     font=(FONT_FAMILY, 8)).pack(side=tk.LEFT)

        canvas_wrap = tk.Frame(frame, bg=COL_BORDER, bd=1)
        canvas_wrap.pack(fill=tk.BOTH, expand=True)

        self.tree_canvas = tk.Canvas(canvas_wrap, bg="#fcfcfc", highlightthickness=0)
        hbar = ttk.Scrollbar(canvas_wrap, orient="horizontal", command=self.tree_canvas.xview)
        vbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.tree_canvas.yview)
        self.tree_canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)

        self.tree_canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        canvas_wrap.rowconfigure(0, weight=1)
        canvas_wrap.columnconfigure(0, weight=1)

        self.tree_canvas.bind("<Configure>", lambda e: self._redraw_tree())
        self._draw_tree_placeholder()

    def _build_output_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, style="Card.TFrame", padding=10)
        nb.add(frame, text="  Resultado  ")

        ttk.Label(frame, text="Texto codificado (copiable / pegable)",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 4))
        wrap = tk.Frame(frame, bg=COL_BORDER, bd=1)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.out_text = scrolledtext.ScrolledText(
            wrap, wrap=tk.WORD, font=("Consolas", 9),
            bg="#ffffff", fg=COL_TEXT, relief="flat", borderwidth=0, padx=10, pady=8,
        )
        self.out_text.pack(fill=tk.BOTH, expand=True)

    # ---------------- arbol ----------------

    def _draw_tree_placeholder(self) -> None:
        self.tree_canvas.delete("all")
        self.tree_canvas.create_text(
            20, 20, anchor="nw",
            text="Codifica o decodifica un archivo para visualizar el arbol.",
            fill=COL_MUTED, font=(FONT_FAMILY, 10),
        )

    def _redraw_tree(self) -> None:
        if self.current_root is None:
            self._draw_tree_placeholder()
            return
        self._draw_tree(self.current_root)

    def _collect_positions(self, root: Node) -> tuple[dict, int]:
        """Asigna x (orden in-order) e y (profundidad) a cada nodo."""
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

        # Limita nodos dibujados para arboles muy grandes (hasta ~200 hojas legibles)
        total = len(positions)
        NODE_LIMIT = 400
        truncated = total > NODE_LIMIT

        x_spacing = max(34, min(60, 900 // max(1, leaf_count)))
        y_spacing = 70
        margin_x, margin_y = 30, 30

        def xy(idx: int, depth: int) -> tuple[int, int]:
            return (margin_x + idx * x_spacing, margin_y + depth * y_spacing)

        # Si truncado, marca cuales dibujar (BFS limitado)
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

        def should_draw(node: Node) -> bool:
            return (not truncated) or id(node) in drawable

        # Dibuja aristas primero
        def draw_edges(node: Node) -> None:
            if node is None or not should_draw(node):
                return
            idx, depth, _ = positions[id(node)]
            x, y = xy(idx, depth)
            for child, label in ((node.left, "0"), (node.right, "1")):
                if child is None or not should_draw(child):
                    continue
                cidx, cdepth, _ = positions[id(child)]
                cx, cy = xy(cidx, cdepth)
                canvas.create_line(x, y, cx, cy, fill=COL_EDGE, width=1.3)
                mx, my = (x + cx) / 2, (y + cy) / 2
                canvas.create_rectangle(mx - 7, my - 8, mx + 7, my + 8,
                                        fill=COL_PANEL, outline="")
                canvas.create_text(mx, my, text=label, fill=COL_ACCENT,
                                   font=(FONT_FAMILY, 8, "bold"))
                draw_edges(child)

        draw_edges(root)

        # Dibuja nodos
        r = 14
        for nid, (idx, depth, node) in positions.items():
            if not should_draw(node):
                continue
            x, y = xy(idx, depth)
            if node.is_leaf:
                canvas.create_oval(x - r, y - r, x + r, y + r,
                                   fill=COL_LEAF, outline="")
                canvas.create_text(x, y, text=str(node.byte), fill="#ffffff",
                                   font=(FONT_FAMILY, 8, "bold"))
                canvas.create_text(x, y + r + 10,
                                   text=f"f={node.freq}", fill=COL_MUTED,
                                   font=(FONT_FAMILY, 8))
            else:
                canvas.create_oval(x - r, y - r, x + r, y + r,
                                   fill=COL_INNER, outline="")
                canvas.create_text(x, y, text=str(node.freq), fill="#ffffff",
                                   font=(FONT_FAMILY, 8))

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
            messagebox.showwarning("Nada que exportar",
                                   "Codifica o decodifica un archivo primero.")
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

        self._status(f"Arbol exportado: {path}")
        messagebox.showinfo("Exportado", f"Arbol guardado en:\n{path}")

    def _render_tree_image(self, Image, ImageDraw, ImageFont):
        root = self.current_root
        positions, max_depth = self._collect_positions(root)
        leaf_count = sum(1 for _, (_, _, n) in positions.items() if n.is_leaf)

        total = len(positions)
        NODE_LIMIT = 400
        truncated = total > NODE_LIMIT

        x_spacing = max(34, min(60, 900 // max(1, leaf_count)))
        y_spacing = 70
        margin_x, margin_y = 30, 30

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

        img = Image.new("RGB", (width, height), "#fcfcfc")
        draw = ImageDraw.Draw(img)

        def load_font(size: int, bold: bool = False):
            for name in ("Montserrat", "Roboto", "arial", "DejaVuSans"):
                for suffix in ((" Bold", "bd.ttf") if bold else ("", ".ttf")):
                    try:
                        return ImageFont.truetype(
                            f"{name}{'-Bold' if bold else ''}.ttf", size)
                    except (OSError, IOError):
                        pass
            try:
                return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)
            except (OSError, IOError):
                return ImageFont.load_default()

        f_leaf = load_font(11, bold=True)
        f_inner = load_font(10)
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
                draw.line((x, y, cx, cy), fill=COL_EDGE, width=2)
                mx, my = (x + cx) // 2, (y + cy) // 2
                draw.rectangle((mx - 8, my - 9, mx + 8, my + 9),
                               fill="#ffffff", outline="#ffffff")
                tw = draw.textlength(label, font=f_edge)
                draw.text((mx - tw / 2, my - 7), label,
                          fill=COL_ACCENT, font=f_edge)
                draw_edges(child)

        draw_edges(root)

        r = 16
        for nid, (idx, depth, node) in positions.items():
            if not show(node):
                continue
            x, y = xy(idx, depth)
            color = COL_LEAF if node.is_leaf else COL_INNER
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
            text = str(node.byte) if node.is_leaf else str(node.freq)
            font = f_leaf if node.is_leaf else f_inner
            tw = draw.textlength(text, font=font)
            draw.text((x - tw / 2, y - r / 2 - 2), text,
                      fill="#ffffff", font=font)
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

    # ---------------- helpers ----------------

    def _reset_steps(self) -> None:
        for lbl in self.step_labels:
            lbl.configure(bg="#e8e8e8", fg=COL_MUTED)

    def _mark_step(self, n: int) -> None:
        if 1 <= n <= len(self.step_labels):
            self.step_labels[n - 1].configure(bg=COL_ACCENT, fg="#ffffff")

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
        self.out_text.delete("1.0", tk.END)
        if len(text) <= DISPLAY_LIMIT:
            self.out_text.insert("1.0", text)
        else:
            self.out_text.insert(
                "1.0",
                text[:DISPLAY_LIMIT]
                + f"\n\n... (mostrando los primeros {DISPLAY_LIMIT} caracteres de {len(text)}. "
                "Usa 'Copiar' o 'Guardar .txt' para obtener el texto completo.)",
            )

    def _status(self, msg: str) -> None:
        self.status_var.set(msg)

    def _update_metrics(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if k in self.metric_vars:
                self.metric_vars[k].set(v)

    def _capture_tree(self, root: Node, codes: dict, freqs: dict) -> None:
        self.current_root = root
        self.current_codes = codes
        self.current_freqs = freqs
        self._redraw_tree()
        self.root.after(50, self._center_tree)

    # ---------------- acciones ----------------

    def load_media(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in MEDIA_EXTENSIONS.split())
        path = filedialog.askopenfilename(
            title="Selecciona imagen o audio",
            filetypes=[("Imagen/Audio", patterns), ("Todos", "*.*")],
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
        self.encoded_text = None
        self.decoded_bytes = None
        self.info_var.set(f"{p.name}  ·  {len(data):,} bytes  ·  {p.suffix or 'desconocido'}")
        self.log_text.delete("1.0", tk.END)
        self.out_text.delete("1.0", tk.END)
        self._reset_steps()
        self.current_root = None
        self._draw_tree_placeholder()
        self._update_metrics(input=f"{len(data):,} B", symbols="—",
                             bits="—", output="—", ratio="—")
        self.log(f"Archivo cargado: {p}")
        self.log(f"Tamano: {len(data)} bytes")
        self._status(f"'{p.name}' cargado. Pulsa 'Codificar'.")

    def do_encode(self) -> None:
        if not self.loaded_bytes:
            messagebox.showwarning("Falta archivo", "Primero carga una imagen o audio.")
            return
        self.log_text.delete("1.0", tk.END)
        self.out_text.delete("1.0", tk.END)
        self._reset_steps()
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            text = encode(self.loaded_bytes, log=self.log, on_tree=self._capture_tree)
        except Exception as e:
            messagebox.showerror("Error codificando", str(e))
            return
        finally:
            self.root.config(cursor="")
        self.encoded_text = text
        self._set_output(text)

        n_in = len(self.loaded_bytes)
        n_out = len(text)
        n_sym = len(self.current_freqs or {})
        bits_total = sum(len(self.current_codes[b]) * f
                         for b, f in (self.current_freqs or {}).items())
        ratio = bits_total / (n_in * 8) * 100 if n_in else 0
        self._update_metrics(
            input=f"{n_in:,} B",
            symbols=str(n_sym),
            bits=f"{bits_total:,}",
            output=f"{n_out:,} ch",
            ratio=f"{ratio:.1f} %",
        )
        self._status(f"Codificacion lista — {n_out:,} caracteres. Revisa el arbol y el resultado.")

    def load_encoded(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona archivo .txt codificado",
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
        self.loaded_bytes = None
        self.decoded_bytes = None
        self._set_output(text)
        self.info_var.set(f"{Path(path).name}  ·  {len(text):,} caracteres codificados")
        self._status("Texto codificado cargado. Pulsa 'Decodificar'.")

    def do_decode(self) -> None:
        text = self.encoded_text
        pasted = self.out_text.get("1.0", tk.END).strip()
        if pasted and (not text or pasted != (text[:DISPLAY_LIMIT] if len(text) > DISPLAY_LIMIT else text)):
            if not text or not pasted.endswith("(mostrando los primeros"):
                text = pasted
        if not text:
            messagebox.showwarning("Nada que decodificar", "Carga o pega un texto codificado primero.")
            return
        self.log_text.delete("1.0", tk.END)
        self._reset_steps()
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            data = decode(text, log=self.log, on_tree=self._capture_tree)
        except Exception as e:
            messagebox.showerror("Error decodificando", str(e))
            return
        finally:
            self.root.config(cursor="")
        self.decoded_bytes = data
        self._update_metrics(
            input=f"{len(text):,} ch",
            symbols=str(len(self.current_freqs or {})),
            bits="—",
            output=f"{len(data):,} B",
            ratio="—",
        )
        self._status(f"Decodificacion OK — {len(data):,} bytes reconstruidos.")
        messagebox.showinfo(
            "Decodificacion OK",
            f"Se reconstruyeron {len(data)} bytes. Guarda con 'Guardar media'.",
        )

    def save_encoded(self) -> None:
        if not self.encoded_text:
            messagebox.showwarning("Nada que guardar", "Primero codifica un archivo.")
            return
        default = "encoded.txt"
        if self.loaded_path:
            default = self.loaded_path.stem + ".huff.txt"
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
        self._status(f"Guardado: {path}")
        messagebox.showinfo("Guardado", f"Archivo guardado en:\n{path}")

    def save_decoded(self) -> None:
        if self.decoded_bytes is None:
            messagebox.showwarning("Nada que guardar", "Primero decodifica un texto codificado.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar media decodificada",
            filetypes=[("Todos", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_bytes(self.decoded_bytes)
        except OSError as e:
            messagebox.showerror("Error al guardar", str(e))
            return
        self._status(f"Media decodificada guardada: {path}")
        messagebox.showinfo("Guardado", f"Archivo guardado en:\n{path}")

    def copy_output(self) -> None:
        if not self.encoded_text:
            messagebox.showwarning("Nada que copiar", "Primero codifica un archivo.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.encoded_text)
        self.root.update()
        self._status(f"Copiado al portapapeles ({len(self.encoded_text):,} caracteres).")

    def clear(self) -> None:
        self.loaded_bytes = None
        self.loaded_path = None
        self.encoded_text = None
        self.decoded_bytes = None
        self.current_root = None
        self.current_codes = None
        self.current_freqs = None
        self.log_text.delete("1.0", tk.END)
        self.out_text.delete("1.0", tk.END)
        self.info_var.set("Sin archivo cargado.")
        self._reset_steps()
        self._update_metrics(input="—", symbols="—", bits="—", output="—", ratio="—")
        self._draw_tree_placeholder()
        self._status("Listo.")


def main() -> None:
    global FONT_FAMILY
    root = tk.Tk()
    FONT_FAMILY = _pick_font()
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
