"""
CALS Type 1 raster support for the C4/MIL PDF dashboard.

CALS Type 1 files are usually stored with .CAL or .CALS extensions and contain
an ASCII header followed by one CCITT Group 4 compressed monochrome raster.
"""

from __future__ import annotations

import io
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - c4_pdf_dashboard already reports Pillow too
    raise SystemExit(
        "Missing dependency: Pillow\n\nInstall it with:\n    py -m pip install pillow\n"
    ) from exc

CALS_EXTENSIONS = {".cal", ".cals"}
CALS_HEADER_SIZE = 2048


class CalsDecodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class CalsMetadata:
    width: int
    height: int
    dpi: int
    rtype: str
    rorient: str
    fields: dict[str, str]


def is_cals(path: Path) -> bool:
    return path.suffix.lower() in CALS_EXTENSIONS


def _parse_fixed_cals_header(header: bytes) -> dict[str, str]:
    """Parse the common 128 byte record CALS header layout."""
    fields: dict[str, str] = {}
    for offset in range(0, min(len(header), CALS_HEADER_SIZE), 128):
        record = header[offset:offset + 128].decode("ascii", errors="ignore").strip()
        if not record or ":" not in record:
            continue
        key, value = record.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key:
            fields[key] = value
    return fields


def parse_cals_metadata(data: bytes, dpi_fallback: int = 300) -> CalsMetadata:
    if len(data) <= CALS_HEADER_SIZE:
        raise CalsDecodeError("File is too small to contain a CALS Type 1 header and image data.")

    fields = _parse_fixed_cals_header(data[:CALS_HEADER_SIZE])
    rtype = fields.get("rtype", "").strip()
    if rtype not in {"1", "01", "001"}:
        raise CalsDecodeError(f"Unsupported or missing CALS rtype: {rtype or '(missing)'}.")

    rpelcnt = fields.get("rpelcnt", "").replace(" ", "")
    match = re.match(r"^(\d+)\s*,\s*(\d+)$", rpelcnt)
    if not match:
        raise CalsDecodeError(f"Could not parse CALS rpelcnt field: {fields.get('rpelcnt', '(missing)')}")

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        raise CalsDecodeError(f"Invalid CALS dimensions: {width} x {height}.")

    density_text = fields.get("rdensty", "").strip()
    try:
        dpi = int(density_text) if density_text else int(dpi_fallback)
    except ValueError:
        dpi = int(dpi_fallback)
    if dpi <= 0:
        dpi = int(dpi_fallback) if dpi_fallback > 0 else 300

    return CalsMetadata(
        width=width,
        height=height,
        dpi=dpi,
        rtype=rtype,
        rorient=fields.get("rorient", ""),
        fields=fields,
    )


def _pack_ifd_entry(tag_id: int, typ: int, count: int, value: int) -> bytes:
    if typ == 3 and count == 1:
        packed_value = struct.pack("<H", value) + b"\0\0"
    else:
        packed_value = struct.pack("<I", value)
    return struct.pack("<HHI", tag_id, typ, count) + packed_value


def _minimal_tiff_from_cals_group4(raw: bytes, width: int, height: int, dpi: int) -> bytes:
    """Wrap a CALS raw CCITT Group 4 strip in a minimal TIFF container for Pillow."""
    tags = [
        (256, 4, 1, width),       # ImageWidth
        (257, 4, 1, height),      # ImageLength
        (258, 3, 1, 1),           # BitsPerSample
        (259, 3, 1, 4),           # Compression: CCITT T.6 / Group 4
        (262, 3, 1, 0),           # PhotometricInterpretation: WhiteIsZero
        (273, 4, 1, 0),           # StripOffsets, patched below
        (278, 4, 1, height),      # RowsPerStrip
        (279, 4, 1, len(raw)),    # StripByteCounts
        (282, 5, 1, 0),           # XResolution, patched below
        (283, 5, 1, 0),           # YResolution, patched below
        (284, 3, 1, 1),           # PlanarConfiguration
        (293, 4, 1, 0),           # T4/T6Options
        (296, 3, 1, 2),           # ResolutionUnit: inch
    ]
    tags.sort()

    ifd_len = 2 + len(tags) * 12 + 4
    rational_offset = 8 + ifd_len
    strip_offset = rational_offset + 16

    out = bytearray(b"II" + struct.pack("<H", 42) + struct.pack("<I", 8))
    out += struct.pack("<H", len(tags))
    for tag_id, typ, count, value in tags:
        if tag_id == 273:
            value = strip_offset
        elif tag_id == 282:
            value = rational_offset
        elif tag_id == 283:
            value = rational_offset + 8
        out += _pack_ifd_entry(tag_id, typ, count, value)
    out += struct.pack("<I", 0)
    out += struct.pack("<II", max(int(dpi), 1), 1)
    out += struct.pack("<II", max(int(dpi), 1), 1)
    out += raw
    return bytes(out)


def decode_cals(path: Path, dpi_fallback: int = 300) -> tuple[Image.Image, str, Tuple[int, int]]:
    data = path.read_bytes()
    meta = parse_cals_metadata(data, dpi_fallback)
    raw = data[CALS_HEADER_SIZE:]
    if not raw:
        raise CalsDecodeError("CALS file has no image data after the 2048 byte header.")

    try:
        image = Image.open(io.BytesIO(_minimal_tiff_from_cals_group4(raw, meta.width, meta.height, meta.dpi)))
        image.load()
        image = image.convert("1")
    except Exception as exc:
        raise CalsDecodeError("Could not decode the CALS CCITT Group 4 raster data.") from exc

    image.info["dpi"] = (meta.dpi, meta.dpi)
    size_inches = f"{meta.width / meta.dpi:.2f} x {meta.height / meta.dpi:.2f} in" if meta.dpi else "unknown"
    info = (
        "CALS Type 1 raster drawing\n"
        "Compression: CCITT Group 4\n"
        f"Pixels: {meta.width:,} x {meta.height:,}\n"
        f"Header DPI: {meta.dpi}\n"
        f"PDF scale: {meta.dpi} dpi = {size_inches}\n"
        f"Header bytes: {CALS_HEADER_SIZE}\n"
        f"Orientation field: {meta.rorient or '(blank)'}"
    )
    return image, info, (meta.dpi, meta.dpi)


def loaded_file(app, path: Path, dpi_fallback: int):
    image, info, dpi = decode_cals(path, dpi_fallback)
    return app.LoadedFile(path, image, dpi, info)
