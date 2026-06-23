"""
MIL/CALS-enabled launcher for the C4 Reader and Converter to PDF dashboard.

This wrapper keeps the original c4_pdf_dashboard.py release code intact and adds
support for JEDMICS .MIL files that contain the same C4/CCITT4 tiled raster data,
CALS Type 1 .CAL/.CALS raster drawings, Group 4 TIFF drawings, and ZIP/WinZip
self extracting EXE package conversion without executing package EXE files.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
import traceback

from PIL import Image, ImageSequence

import c4_pdf_dashboard as app
import c4_sfx_package_support
import cals_raster_support

C4_MIL_EXTENSIONS = {".c4", ".mil"}
TIFF_EXTENSIONS = {".tif", ".tiff"}
IMAGE_EXTENSIONS = {
    ".tif", ".tiff",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
    ".pbm", ".pgm", ".ppm",
}
DRAWING_EXTENSIONS = C4_MIL_EXTENSIONS | cals_raster_support.CALS_EXTENSIONS
PACKAGE_CONTENT_EXTENSIONS = DRAWING_EXTENSIONS | IMAGE_EXTENSIONS

app.APP_TITLE = "C4/MIL/CALS Reader and Converter to PDF"
app.SUPPORTED_EXTENSIONS.update(PACKAGE_CONTENT_EXTENSIONS)

_original_load_file = app.load_file
_original_convert_file_to_pdf = app.convert_file_to_pdf
_original_dashboard_init = app.Dashboard.__init__


def _is_c4_or_mil(path: Path) -> bool:
    return path.suffix.lower() in C4_MIL_EXTENSIONS


def _is_cals(path: Path) -> bool:
    return cals_raster_support.is_cals(path)


def _is_tiff(path: Path) -> bool:
    return path.suffix.lower() in TIFF_EXTENSIONS


def _pdf_safe_image(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        return background
    if image.mode not in ("1", "L", "RGB"):
        return image.convert("RGB")
    return image


def _dpi_from_image(image: Image.Image, fallback: int) -> tuple[int, int]:
    dpi = image.info.get("dpi", (fallback, fallback))
    try:
        dpi = (int(round(float(dpi[0]))), int(round(float(dpi[1]))))
    except Exception:
        dpi = (fallback, fallback)
    return (dpi[0] or fallback, dpi[1] or fallback)


def save_tiff_as_pdf(path: Path, out_path: Path, dpi_fallback: int = app.DEFAULT_DPI) -> None:
    """Save every frame/page from a TIFF as a multi-page PDF."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as image:
        dpi = _dpi_from_image(image, dpi_fallback)
        pages = []
        for frame in ImageSequence.Iterator(image):
            pages.append(_pdf_safe_image(frame.copy()))
        if not pages:
            raise RuntimeError(f"No image frames found in TIFF: {path}")
        first, rest = pages[0], pages[1:]
        first.save(out_path, "PDF", resolution=float(dpi[0]), save_all=bool(rest), append_images=rest)


def _tiff_page_count(path: Path) -> int:
    try:
        with Image.open(path) as image:
            return int(getattr(image, "n_frames", 1))
    except Exception:
        return 1


def load_file(path: Path, dpi_fallback: int = app.DEFAULT_DPI) -> app.LoadedFile:
    if _is_c4_or_mil(path):
        image, info, dpi = app.decode_c4(path, dpi_fallback)
        if path.suffix.lower() == ".mil":
            info = info.replace("C4/JEDMICS raster drawing", "JEDMICS MIL raster drawing")
        return app.LoadedFile(path, image, dpi, info)
    if _is_cals(path):
        return cals_raster_support.loaded_file(app, path, dpi_fallback)
    loaded = _original_load_file(path, dpi_fallback)
    if _is_tiff(path) and loaded.image is not None:
        page_count = _tiff_page_count(path)
        if page_count > 1:
            loaded.info += f"\nPages: {page_count}\nPDF export: all TIFF pages are saved. Preview shows the first page."
    return loaded


def convert_file_to_pdf(path: Path, out_path: Path, dpi_fallback: int = app.DEFAULT_DPI) -> tuple[bool, str]:
    try:
        if _is_tiff(path):
            save_tiff_as_pdf(path, out_path, dpi_fallback)
            return True, str(out_path)
        loaded = load_file(path, dpi_fallback)
        if loaded.image is None:
            return False, "No image data available for conversion."
        dpi = loaded.dpi
        if _is_c4_or_mil(path):
            dpi = (dpi_fallback, dpi_fallback)
        app.save_image_as_pdf(loaded.image, out_path, dpi)
        return True, str(out_path)
    except Exception as exc:
        return False, str(exc)


def dashboard_init(self: app.Dashboard) -> None:
    _original_dashboard_init(self)
    self.title(app.APP_TITLE)
    try:
        self.status_var.set("Select a C4, MIL, CALS, TIFF, image, ZIP, or self extracting EXE package.")
    except Exception:
        pass


def select_file(self: app.Dashboard) -> None:
    filetypes = [
        (
            "Supported files",
            "*.c4 *.C4 *.mil *.MIL *.cal *.CAL *.cals *.CALS *.exe *.EXE *.zip *.ZIP *.tif *.TIF *.tiff *.TIFF *.png *.jpg *.jpeg *.bmp *.gif *.webp *.pbm *.pgm *.ppm *.pdf",
        ),
        ("C4/MIL/CALS drawings", "*.c4 *.C4 *.mil *.MIL *.cal *.CAL *.cals *.CALS"),
        ("ZIP/SFX packages", "*.exe *.EXE *.zip *.ZIP"),
        ("TIFF drawings", "*.tif *.TIF *.tiff *.TIFF"),
        ("Images", "*.tif *.tiff *.png *.jpg *.jpeg *.bmp *.gif *.webp *.pbm *.pgm *.ppm"),
        ("PDF", "*.pdf"),
        ("All files", "*.*"),
    ]
    selected = filedialog.askopenfilename(title="Select file", filetypes=filetypes)
    if selected:
        self.load_selected(Path(selected))


def load_selected(self: app.Dashboard, path: Path) -> None:
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


def save_pdf(self: app.Dashboard) -> None:
    if self.loaded is None:
        messagebox.showinfo("No file selected", "Select a file first.")
        return
    default_name = self.loaded.path.stem + ".pdf"
    out = filedialog.asksaveasfilename(
        title="Save PDF",
        defaultextension=".pdf",
        initialfile=default_name,
        filetypes=[("PDF files", "*.pdf")],
    )
    if not out:
        return
    out_path = Path(out)
    try:
        if self.loaded.path.suffix.lower() == ".pdf" and self.loaded.image is None:
            out_path.write_bytes(self.loaded.path.read_bytes())
        elif _is_tiff(self.loaded.path):
            save_tiff_as_pdf(self.loaded.path, out_path, int(self.dpi_var.get()))
        elif self.loaded.image is not None:
            dpi = self.loaded.dpi
            if _is_c4_or_mil(self.loaded.path):
                dpi = (int(self.dpi_var.get()), int(self.dpi_var.get()))
            app.save_image_as_pdf(self.loaded.image, out_path, dpi)
        else:
            raise RuntimeError("No image data is available to export.")
    except Exception as exc:
        self.status_var.set("Save failed.")
        messagebox.showerror("Save failed", f"Could not save PDF:\n{out_path}\n\n{exc}\n\n{traceback.format_exc()}")
        return
    self.status_var.set(f"Saved PDF: {out_path}")
    if self.open_after_save.get():
        app.open_default(out_path)


app.load_file = load_file
app.convert_file_to_pdf = convert_file_to_pdf
app.Dashboard.__init__ = dashboard_init
app.Dashboard.select_file = select_file
app.Dashboard.load_selected = load_selected
app.Dashboard.save_pdf = save_pdf

c4_sfx_package_support.install(app, PACKAGE_CONTENT_EXTENSIONS)


if __name__ == "__main__":
    app.main()
