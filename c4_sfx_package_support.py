"""
ZIP and WinZip self extracting EXE package support for the C4/MIL dashboard.

Package EXE files are treated as archives only. They are opened with Python's
zipfile module, which can read ZIP data that has a self extractor stub prepended.
The EXE is never executed.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from tkinter import filedialog, messagebox
import traceback
import zipfile

PACKAGE_EXTENSIONS = {".exe", ".zip"}


def _is_package(path: Path) -> bool:
    return path.suffix.lower() in PACKAGE_EXTENSIONS


def _safe_relative_parts(name: str) -> list[str]:
    parts = Path(name.replace("\\", "/")).parts
    safe: list[str] = []
    for part in parts:
        if part in {"", ".", ".."}:
            continue
        if ":" in part:
            continue
        safe.append(part)
    return safe


def _package_drawings(package_path: Path, drawing_extensions: set[str]) -> list[zipfile.ZipInfo]:
    try:
        with zipfile.ZipFile(package_path) as archive:
            drawings = [
                info
                for info in archive.infolist()
                if not info.is_dir() and Path(info.filename).suffix.lower() in drawing_extensions
            ]
    except zipfile.BadZipFile as exc:
        raise RuntimeError(
            f"This file is not a readable ZIP or WinZip self extracting archive:\n{package_path}"
        ) from exc
    drawings.sort(key=lambda info: info.filename.lower())
    return drawings


def _temp_file_from_entry(package_path: Path, entry: zipfile.ZipInfo) -> Path:
    with zipfile.ZipFile(package_path) as archive:
        data = archive.read(entry)
    suffix = Path(entry.filename).suffix.lower() or ".c4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(data)
        return Path(temp.name)


def _decode_package_entry(app, package_path: Path, entry: zipfile.ZipInfo, dpi_fallback: int):
    temp_path = _temp_file_from_entry(package_path, entry)
    try:
        image, info, dpi = app.decode_c4(temp_path, dpi_fallback)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    info = (
        "ZIP/SFX package entry\n"
        f"Package: {package_path}\n"
        f"Entry: {entry.filename}\n\n"
        f"{info}"
    )
    return app.LoadedFile(package_path, image, dpi, info)


def _output_path_for_package_entry(package_path: Path, entry_name: str) -> Path:
    output_root = package_path.with_name(package_path.stem + "_pdfs")
    parts = _safe_relative_parts(entry_name)
    if not parts:
        parts = ["drawing.c4"]
    *folders, leaf = parts
    return output_root.joinpath(*folders, Path(leaf).with_suffix(".pdf"))


def install(app, drawing_extensions: set[str]) -> None:
    """Install package handling into the existing dashboard module."""
    app.SUPPORTED_EXTENSIONS.update(PACKAGE_EXTENSIONS)

    original_load_file = app.load_file
    original_convert_file_to_pdf = app.convert_file_to_pdf
    original_dashboard_init = app.Dashboard.__init__

    def load_file(path: Path, dpi_fallback: int = app.DEFAULT_DPI):
        if _is_package(path):
            drawings = _package_drawings(path, drawing_extensions)
            if not drawings:
                raise RuntimeError("This package does not contain any .C4 or .MIL drawing files.")
            if len(drawings) > 1:
                names = "\n".join(f"- {info.filename}" for info in drawings[:25])
                more = "" if len(drawings) <= 25 else f"\n...and {len(drawings) - 25} more"
                raise RuntimeError(
                    "This package contains multiple C4/MIL drawings. "
                    "Use Batch convert folder to convert package contents.\n\n"
                    f"Found {len(drawings)} drawing file(s):\n{names}{more}"
                )
            return _decode_package_entry(app, path, drawings[0], dpi_fallback)
        return original_load_file(path, dpi_fallback)

    def convert_file_to_pdf(path: Path, out_path: Path, dpi_fallback: int = app.DEFAULT_DPI) -> tuple[bool, str]:
        if not _is_package(path):
            return original_convert_file_to_pdf(path, out_path, dpi_fallback)
        try:
            drawings = _package_drawings(path, drawing_extensions)
            if not drawings:
                return False, "No .C4 or .MIL drawing files found in package."
            if len(drawings) != 1:
                return False, "Package has multiple drawings. Use Batch convert folder for package contents."
            loaded = _decode_package_entry(app, path, drawings[0], dpi_fallback)
            app.save_image_as_pdf(loaded.image, out_path, (dpi_fallback, dpi_fallback))
            return True, str(out_path)
        except Exception as exc:
            return False, str(exc)

    def _convert_package_to_pdfs(package_path: Path, dpi: int, overwrite: bool) -> tuple[int, int, int, list[str]]:
        try:
            drawings = _package_drawings(package_path, drawing_extensions)
        except Exception as exc:
            return 0, 0, 1, [f"FAIL package: {package_path} :: {exc}"]
        if not drawings:
            return 0, 0, 1, [f"FAIL package: {package_path} :: no .C4 or .MIL drawing files found"]

        converted = skipped = failed = 0
        logs = [f"PACKAGE: {package_path} ({len(drawings)} C4/MIL file(s))"]
        for entry in drawings:
            out_path = _output_path_for_package_entry(package_path, entry.filename)
            if out_path.exists() and not overwrite:
                skipped += 1
                logs.append(f"SKIP existing: {out_path}")
                continue

            temp_path: Path | None = None
            try:
                temp_path = _temp_file_from_entry(package_path, entry)
                ok, note = original_convert_file_to_pdf(temp_path, out_path, dpi)
                if ok:
                    converted += 1
                    logs.append(f"OK: {package_path.name}/{entry.filename} -> {out_path}")
                else:
                    failed += 1
                    logs.append(f"FAIL: {package_path.name}/{entry.filename} :: {note}")
            except Exception as exc:
                failed += 1
                logs.append(f"FAIL: {package_path.name}/{entry.filename} :: {exc}")
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
        return converted, skipped, failed, logs

    def dashboard_init(self) -> None:
        original_dashboard_init(self)
        try:
            self.status_var.set("Select a C4, MIL, image, ZIP, or self extracting EXE package.")
        except Exception:
            pass

    def select_file(self) -> None:
        filetypes = [
            (
                "Supported files",
                "*.c4 *.C4 *.mil *.MIL *.exe *.EXE *.zip *.ZIP *.tif *.tiff *.png *.jpg *.jpeg *.bmp *.gif *.webp *.pbm *.pgm *.ppm *.pdf",
            ),
            ("C4/MIL drawings", "*.c4 *.C4 *.mil *.MIL"),
            ("ZIP/SFX packages", "*.exe *.EXE *.zip *.ZIP"),
            ("Images", "*.tif *.tiff *.png *.jpg *.jpeg *.bmp *.gif *.webp *.pbm *.pgm *.ppm"),
            ("PDF", "*.pdf"),
            ("All files", "*.*"),
        ]
        selected = filedialog.askopenfilename(title="Select file", filetypes=filetypes)
        if selected:
            self.load_selected(Path(selected))

    def load_selected(self, path: Path) -> None:
        try:
            loaded = app.load_file(path, int(self.dpi_var.get()))
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

    def batch_worker(self, root_path: Path, dpi: int, overwrite: bool) -> None:
        try:
            files = []
            for current_root, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in {".git", ".svn", ".hg", "__pycache__"}]
                for name in filenames:
                    p = Path(current_root) / name
                    if p.suffix.lower() in app.SUPPORTED_EXTENSIONS:
                        files.append(p)
            files.sort(key=lambda p: str(p).lower())
        except Exception as exc:
            self.batch_queue.put(("fatal", f"Directory scan failed: {exc}"))
            return

        total = len(files)
        self.batch_queue.put(("total", total))
        converted = skipped = failed = 0
        for index, path in enumerate(files, start=1):
            if _is_package(path):
                c, s, f, logs = _convert_package_to_pdfs(path, dpi, overwrite)
                converted += c
                skipped += s
                failed += f
                for log in logs:
                    self.batch_queue.put(("log", log))
            else:
                out_path = path.with_suffix(".pdf")
                if out_path.exists() and not overwrite:
                    skipped += 1
                    self.batch_queue.put(("log", f"SKIP existing: {out_path}"))
                else:
                    ok, note = app.convert_file_to_pdf(path, out_path, dpi)
                    if ok:
                        converted += 1
                        self.batch_queue.put(("log", f"OK: {path} -> {out_path.name}"))
                    else:
                        failed += 1
                        self.batch_queue.put(("log", f"FAIL: {path} :: {note}"))
            self.batch_queue.put(("progress", index, total))
        self.batch_queue.put(("done", converted, skipped, failed))

    app.load_file = load_file
    app.convert_file_to_pdf = convert_file_to_pdf
    app.Dashboard.__init__ = dashboard_init
    app.Dashboard.select_file = select_file
    app.Dashboard.load_selected = load_selected
    app.Dashboard._batch_worker = batch_worker
