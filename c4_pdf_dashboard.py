"""
C4 Reader and Converter to PDF

Tkinter dashboard for opening C4/JEDMICS raster drawings or normal images,
previewing them, saving them to PDF, and recursively batch converting a folder
so PDFs are written beside each source file.
"""

from __future__ import annotations

import io
import math
import os
import queue
import struct
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: Pillow\n\nInstall it with:\n    py -m pip install pillow\n"
    ) from exc

APP_TITLE = "C4 Reader and Converter to PDF"
DEFAULT_DPI = 200
TILE_SIZE = 512
SUPPORTED_EXTENSIONS = {
    ".c4",
    ".tif", ".tiff",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
    ".pbm", ".pgm", ".ppm",
}


@dataclass
class LoadedFile:
    path: Path
    image: Optional[Image.Image]
    dpi: Tuple[int, int]
    info: str


class C4DecodeError(RuntimeError):
    pass


def _minimal_tiff_from_group4(raw: bytes, width: int = TILE_SIZE, height: int = TILE_SIZE) -> bytes:
    """Wrap raw CCITT Group 4 bytes in a minimal TIFF container for Pillow."""
    tags = []

    def add(tag_id: int, typ: int, count: int, value: int) -> None:
        tags.append((tag_id, typ, count, value))

    add(256, 4, 1, width)        # ImageWidth
    add(257, 4, 1, height)       # ImageLength
    add(258, 3, 1, 1)            # BitsPerSample
    add(259, 3, 1, 4)            # Compression: CCITT T.6 / Group 4
    add(262, 3, 1, 0)            # PhotometricInterpretation: WhiteIsZero
    add(273, 4, 1, 0)            # StripOffsets, patched below
    add(278, 4, 1, height)       # RowsPerStrip
    add(279, 4, 1, len(raw))     # StripByteCounts
    add(284, 3, 1, 1)            # PlanarConfiguration
    add(293, 4, 1, 0)            # T4/T6Options

    tags.sort()
    header_len = 8 + 2 + len(tags) * 12 + 4
    out = bytearray(b"II" + struct.pack("<H", 42) + struct.pack("<I", 8))
    out += struct.pack("<H", len(tags))

    for tag_id, typ, count, value in tags:
        if tag_id == 273:
            value = header_len
        if typ == 3 and count == 1:
            packed = struct.pack("<H", value) + b"\0\0"
        else:
            packed = struct.pack("<I", value)
        out += struct.pack("<HHI", tag_id, typ, count) + packed

    out += struct.pack("<I", 0)
    out += raw
    return bytes(out)


def decode_c4(path: Path, dpi: int = DEFAULT_DPI) -> tuple[Image.Image, str, tuple[int, int]]:
    """
    Decode the common tiled C4/JEDMICS raster drawing format.

    Layout handled here:
    - byte 0: little endian uint32 index offset
    - byte 4: little endian uint16 image height
    - byte 6: little endian uint16 bytes wide, so pixel width = bytes wide * 8
    - byte 8: big endian uint32 tile payload offset
    - byte 12: tile count, or 0 when it should be derived from dimensions
    - each tile index entry: tile number, compression flag, little endian uint16 byte count
    - tile size: 512 x 512 pixels
    - compression flag 0x00: CCITT Group 4
    - compression flag 0x80: raw 1 bpp tile
    """
    data = path.read_bytes()
    if len(data) < 16:
        raise C4DecodeError("File is too small to be a supported C4 drawing.")

    try:
        index_offset = struct.unpack_from("<I", data, 0)[0]
        height = struct.unpack_from("<H", data, 4)[0]
        bytes_wide = struct.unpack_from("<H", data, 6)[0]
        data_offset = struct.unpack_from(">I", data, 8)[0]
        tile_count = data[12]
    except struct.error as exc:
        raise C4DecodeError("Could not parse C4 header.") from exc

    width = bytes_wide * 8
    if width <= 0 or height <= 0:
        raise C4DecodeError(f"Invalid C4 dimensions: {width} x {height}.")
    if not (0 < index_offset < len(data)):
        raise C4DecodeError(f"Invalid C4 index offset: {index_offset}.")
    if not (0 < data_offset <= len(data)):
        raise C4DecodeError(f"Invalid C4 data offset: {data_offset}.")

    cols = math.ceil(width / TILE_SIZE)
    rows = math.ceil(height / TILE_SIZE)
    expected_tiles = cols * rows
    if tile_count == 0:
        tile_count = expected_tiles
    if tile_count != expected_tiles:
        raise C4DecodeError(
            f"Tile count mismatch. Header says {tile_count}, but dimensions require {expected_tiles}."
        )

    entries = []
    index_pos = index_offset
    payload_pos = data_offset
    for entry_no in range(tile_count):
        if index_pos + 4 > len(data):
            raise C4DecodeError(f"Tile index ended early at entry {entry_no}.")
        tile_no = data[index_pos]
        compression = data[index_pos + 1]
        size = struct.unpack_from("<H", data, index_pos + 2)[0]
        if size <= 0:
            raise C4DecodeError(f"Tile {entry_no} has invalid payload size {size}.")
        if payload_pos + size > len(data):
            raise C4DecodeError(f"Tile {entry_no} payload extends beyond end of file.")
        entries.append((tile_no, compression, payload_pos, size))
        payload_pos += size
        index_pos += 4

    full = Image.new("1", (cols * TILE_SIZE, rows * TILE_SIZE), 1)

    for idx, (tile_no, compression, payload_pos, size) in enumerate(entries):
        logical_tile = idx if tile_count > 252 else tile_no
        col = logical_tile % cols
        row = logical_tile // cols
        raw = data[payload_pos:payload_pos + size]

        if compression == 0x80:
            expected_raw = TILE_SIZE * TILE_SIZE // 8
            if len(raw) != expected_raw:
                raise C4DecodeError(f"Raw tile {idx} has {len(raw)} bytes; expected {expected_raw}.")
            tile = Image.frombytes("1", (TILE_SIZE, TILE_SIZE), raw)
        elif compression == 0x00:
            tile = Image.open(io.BytesIO(_minimal_tiff_from_group4(raw)))
            tile.load()
            tile = tile.convert("1")
        else:
            raise C4DecodeError(f"Unsupported tile compression flag 0x{compression:02X} at tile {idx}.")

        full.paste(tile, (col * TILE_SIZE, row * TILE_SIZE))

    full = full.crop((0, 0, width, height))
    full.info["dpi"] = (dpi, dpi)
    info = (
        "C4/JEDMICS raster drawing\n"
        f"Pixels: {width:,} x {height:,}\n"
        f"Tiles: {cols} columns x {rows} rows = {tile_count}\n"
        f"PDF scale: {dpi} dpi = {width / dpi:.2f} x {height / dpi:.2f} in"
    )
    return full, info, (dpi, dpi)


def render_pdf_preview(path: Path) -> Optional[Image.Image]:
    """Render the first page of a PDF for preview if PyMuPDF is installed."""
    try:
        import fitz  # type: ignore
    except Exception:
        return None

    with fitz.open(path) as doc:
        if doc.page_count == 0:
            return None
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def load_file(path: Path, dpi_fallback: int = DEFAULT_DPI) -> LoadedFile:
    suffix = path.suffix.lower()
    if suffix == ".c4":
        image, info, dpi = decode_c4(path, dpi_fallback)
        return LoadedFile(path, image, dpi, info)

    if suffix == ".pdf":
        preview = render_pdf_preview(path)
        if preview is None:
            return LoadedFile(
                path,
                None,
                (dpi_fallback, dpi_fallback),
                "PDF selected. Install optional PyMuPDF to preview PDFs inside the dashboard.",
            )
        return LoadedFile(path, preview, (dpi_fallback, dpi_fallback), "PDF preview rendered from first page.")

    try:
        image = Image.open(path)
        image.load()
    except Exception as exc:
        raise RuntimeError(f"Could not open this as a supported image or C4 file:\n{path}") from exc

    dpi = image.info.get("dpi", (dpi_fallback, dpi_fallback))
    try:
        dpi = (int(round(float(dpi[0]))), int(round(float(dpi[1]))))
    except Exception:
        dpi = (dpi_fallback, dpi_fallback)
    dpi = (dpi[0] or dpi_fallback, dpi[1] or dpi_fallback)

    info = (
        "Image file\n"
        f"Format: {image.format or suffix.upper().lstrip('.')}\n"
        f"Mode: {image.mode}\n"
        f"Pixels: {image.width:,} x {image.height:,}\n"
        f"DPI: {dpi[0]} x {dpi[1]}"
    )
    return LoadedFile(path, image, dpi, info)


def save_image_as_pdf(image: Image.Image, out_path: Path, dpi: Tuple[int, int]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = image
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.getchannel("A"))
        img = background
    elif img.mode not in ("1", "L", "RGB"):
        img = img.convert("RGB")
    img.save(out_path, "PDF", resolution=float(dpi[0]))


def convert_file_to_pdf(path: Path, out_path: Path, dpi_fallback: int = DEFAULT_DPI) -> tuple[bool, str]:
    try:
        loaded = load_file(path, dpi_fallback)
        if loaded.image is None:
            return False, "No image data available for conversion."
        dpi = (dpi_fallback, dpi_fallback) if path.suffix.lower() == ".c4" else loaded.dpi
        save_image_as_pdf(loaded.image, out_path, dpi)
        return True, str(out_path)
    except Exception as exc:
        return False, str(exc)


def open_default(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


class Dashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1220x820")
        self.minsize(920, 620)

        self.loaded: Optional[LoadedFile] = None
        self.preview_base: Optional[Image.Image] = None
        self.preview_tk: Optional[ImageTk.PhotoImage] = None
        self.batch_queue: "queue.Queue[tuple]" = queue.Queue()
        self.batch_running = False

        self.dpi_var = tk.IntVar(value=DEFAULT_DPI)
        self.zoom_var = tk.DoubleVar(value=0.20)
        self.open_after_save = tk.BooleanVar(value=True)
        self.overwrite_existing = tk.BooleanVar(value=False)
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Select a C4 drawing or image file.")

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=12)
        left.grid(row=0, column=0, sticky="ns")
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="C4 PDF Dashboard", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(left, text="Select file...", command=self.select_file).grid(row=1, column=0, sticky="ew", pady=(14, 4))
        ttk.Button(left, text="Save selected as PDF...", command=self.save_pdf).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(left, text="Open selected externally", command=self.open_selected_externally).grid(row=3, column=0, sticky="ew", pady=4)
        self.batch_button = ttk.Button(left, text="Batch convert folder...", command=self.batch_convert_folder)
        self.batch_button.grid(row=4, column=0, sticky="ew", pady=(12, 4))

        options = ttk.LabelFrame(left, text="Options", padding=10)
        options.grid(row=5, column=0, sticky="ew", pady=(12, 4))
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="C4 DPI").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(options, from_=72, to=600, textvariable=self.dpi_var, width=8).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Checkbutton(options, text="Open PDF after saving", variable=self.open_after_save).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(options, text="Overwrite PDFs in batch", variable=self.overwrite_existing).grid(row=2, column=0, columnspan=2, sticky="w")

        progress = ttk.LabelFrame(left, text="Batch progress", padding=10)
        progress.grid(row=6, column=0, sticky="ew", pady=(12, 4))
        ttk.Progressbar(progress, variable=self.progress_var, maximum=100).grid(row=0, column=0, sticky="ew")
        progress.columnconfigure(0, weight=1)

        ttk.Label(left, text="Details / log", font=("Segoe UI", 11, "bold")).grid(row=7, column=0, sticky="w", pady=(12, 4))
        self.details = tk.Text(left, width=44, height=22, wrap="word")
        self.details.grid(row=8, column=0, sticky="nsew")
        left.rowconfigure(8, weight=1)

        right = ttk.Frame(self, padding=(0, 12, 12, 12))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        zoom_frame = ttk.Frame(right)
        zoom_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(zoom_frame, text="Zoom").pack(side="left")
        ttk.Scale(zoom_frame, from_=0.04, to=1.0, variable=self.zoom_var, command=lambda _v: self.update_preview()).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(zoom_frame, text="Fit", command=self.fit_preview).pack(side="left")

        canvas_frame = ttk.Frame(right)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(canvas_frame, background="#2b2b2b")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.canvas.bind("<MouseWheel>", self._mousewheel)

        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew")

    def select_file(self) -> None:
        filetypes = [
            ("Supported files", "*.c4 *.C4 *.tif *.tiff *.png *.jpg *.jpeg *.bmp *.gif *.webp *.pbm *.pgm *.ppm *.pdf"),
            ("C4 drawings", "*.c4 *.C4"),
            ("Images", "*.tif *.tiff *.png *.jpg *.jpeg *.bmp *.gif *.webp *.pbm *.pgm *.ppm"),
            ("PDF", "*.pdf"),
            ("All files", "*.*"),
        ]
        selected = filedialog.askopenfilename(title="Select file", filetypes=filetypes)
        if selected:
            self.load_selected(Path(selected))

    def load_selected(self, path: Path) -> None:
        try:
            loaded = load_file(path, int(self.dpi_var.get()))
        except Exception as exc:
            self.status_var.set("Load failed.")
            messagebox.showerror("Load failed", f"Could not load file:\n{path}\n\n{exc}\n\n{traceback.format_exc()}")
            return

        self.loaded = loaded
        self.preview_base = loaded.image.copy() if loaded.image is not None else None
        self.set_details(f"File:\n{path}\n\n{loaded.info}\n")
        if self.preview_base is None:
            self.canvas.delete("all")
            self.canvas.create_text(20, 20, text=loaded.info, fill="white", anchor="nw", font=("Segoe UI", 13), width=700)
            self.status_var.set(f"Loaded {path.name}; no internal preview available.")
        else:
            self.fit_preview()
            self.status_var.set(f"Loaded {path.name}; ready to save as PDF.")

    def save_pdf(self) -> None:
        if self.loaded is None:
            messagebox.showinfo("No file selected", "Select a file first.")
            return
        default_name = self.loaded.path.stem + ".pdf"
        out = filedialog.asksaveasfilename(title="Save PDF", defaultextension=".pdf", initialfile=default_name, filetypes=[("PDF files", "*.pdf")])
        if not out:
            return
        out_path = Path(out)
        try:
            if self.loaded.path.suffix.lower() == ".pdf" and self.loaded.image is None:
                out_path.write_bytes(self.loaded.path.read_bytes())
            elif self.loaded.image is not None:
                dpi = self.loaded.dpi
                if self.loaded.path.suffix.lower() == ".c4":
                    dpi = (int(self.dpi_var.get()), int(self.dpi_var.get()))
                save_image_as_pdf(self.loaded.image, out_path, dpi)
            else:
                raise RuntimeError("No image data is available to export.")
        except Exception as exc:
            self.status_var.set("Save failed.")
            messagebox.showerror("Save failed", f"Could not save PDF:\n{out_path}\n\n{exc}\n\n{traceback.format_exc()}")
            return
        self.status_var.set(f"Saved PDF: {out_path}")
        if self.open_after_save.get():
            open_default(out_path)

    def batch_convert_folder(self) -> None:
        if self.batch_running:
            messagebox.showinfo("Batch already running", "A batch conversion is already running.")
            return
        root = filedialog.askdirectory(title="Select root folder to batch convert")
        if not root:
            return
        root_path = Path(root)
        self.batch_running = True
        self.batch_button.configure(state="disabled")
        self.progress_var.set(0)
        self.set_details(
            f"Batch root:\n{root_path}\n\n"
            "Mode: recursive through all subfolders\n"
            "Output: same folder as source, same base name, .pdf extension\n"
            f"Overwrite existing PDFs: {'yes' if self.overwrite_existing.get() else 'no'}\n\n"
        )
        threading.Thread(
            target=self._batch_worker,
            args=(root_path, int(self.dpi_var.get()), bool(self.overwrite_existing.get())),
            daemon=True,
        ).start()
        self.after(100, self._process_batch_queue)

    def _batch_worker(self, root_path: Path, dpi: int, overwrite: bool) -> None:
        try:
            files = []
            for current_root, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in {".git", ".svn", ".hg", "__pycache__"}]
                for name in filenames:
                    p = Path(current_root) / name
                    if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                        files.append(p)
            files.sort(key=lambda p: str(p).lower())
        except Exception as exc:
            self.batch_queue.put(("fatal", f"Directory scan failed: {exc}"))
            return

        total = len(files)
        self.batch_queue.put(("total", total))
        converted = skipped = failed = 0
        for index, path in enumerate(files, start=1):
            out_path = path.with_suffix(".pdf")
            if out_path.exists() and not overwrite:
                skipped += 1
                self.batch_queue.put(("log", f"SKIP existing: {out_path}"))
            else:
                ok, note = convert_file_to_pdf(path, out_path, dpi)
                if ok:
                    converted += 1
                    self.batch_queue.put(("log", f"OK: {path} -> {out_path.name}"))
                else:
                    failed += 1
                    self.batch_queue.put(("log", f"FAIL: {path} :: {note}"))
            self.batch_queue.put(("progress", index, total))
        self.batch_queue.put(("done", converted, skipped, failed))

    def _process_batch_queue(self) -> None:
        try:
            while True:
                item = self.batch_queue.get_nowait()
                kind = item[0]
                if kind == "total":
                    self.append_details(f"Found {item[1]} supported source file(s).\n")
                elif kind == "progress":
                    done, total = item[1], item[2]
                    self.progress_var.set(0 if total == 0 else done / total * 100)
                    self.status_var.set(f"Batch progress: {done}/{total}")
                elif kind == "log":
                    self.append_details(item[1] + "\n")
                elif kind == "fatal":
                    self.append_details("ERROR: " + item[1] + "\n")
                    self.batch_running = False
                    self.batch_button.configure(state="normal")
                    self.status_var.set("Batch conversion failed.")
                    messagebox.showerror("Batch conversion failed", item[1])
                    return
                elif kind == "done":
                    converted, skipped, failed = item[1], item[2], item[3]
                    summary = f"Converted {converted}, skipped {skipped}, failed {failed}."
                    self.append_details("\n" + summary + "\n")
                    self.batch_running = False
                    self.batch_button.configure(state="normal")
                    self.status_var.set("Batch complete. " + summary)
                    return
        except queue.Empty:
            pass
        if self.batch_running:
            self.after(100, self._process_batch_queue)

    def open_selected_externally(self) -> None:
        if self.loaded is None:
            messagebox.showinfo("No file selected", "Select a file first.")
            return
        open_default(self.loaded.path)

    def fit_preview(self) -> None:
        if self.preview_base is None:
            return
        self.update_idletasks()
        cw = max(self.canvas.winfo_width() - 40, 100)
        ch = max(self.canvas.winfo_height() - 40, 100)
        scale = min(cw / self.preview_base.width, ch / self.preview_base.height, 1.0)
        self.zoom_var.set(max(scale, 0.04))
        self.update_preview()

    def update_preview(self) -> None:
        if self.preview_base is None:
            return
        scale = float(self.zoom_var.get())
        preview = self.preview_base
        if preview.mode not in ("RGB", "RGBA"):
            preview = preview.convert("RGB")
        preview = ImageOps.expand(preview, border=8, fill="white")
        width = max(1, int(preview.width * scale))
        height = max(1, int(preview.height * scale))
        resampling = Image.Resampling.LANCZOS if scale < 1 else Image.Resampling.NEAREST
        preview = preview.resize((width, height), resampling)
        self.preview_tk = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_image(20, 20, image=self.preview_tk, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, width + 40, height + 40))

    def _mousewheel(self, event: tk.Event) -> None:
        if event.state & 0x0004:
            factor = 1.10 if event.delta > 0 else 0.90
            self.zoom_var.set(min(1.0, max(0.04, float(self.zoom_var.get()) * factor)))
            self.update_preview()
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_details(self, text: str) -> None:
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def append_details(self, text: str) -> None:
        self.details.configure(state="normal")
        self.details.insert("end", text)
        self.details.see("end")
        self.details.configure(state="disabled")


def main() -> None:
    app = Dashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
