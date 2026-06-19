# C4 Reader and Converter to PDF

Local Windows friendly Python dashboard for opening C4/JEDMICS raster drawings and converting them to PDF.

## Features

- Select a single C4 drawing or normal image file.
- Preview the decoded drawing on the right side with scroll and zoom.
- Save the selected drawing as a PDF.
- Batch convert a whole directory tree.
- Recursive batch mode searches all subfolders and writes each PDF beside the source file.
- Existing PDFs are skipped by default unless overwrite is enabled.

## Supported input formats

Direct conversion:

- `.C4` / `.c4` JEDMICS tiled CCITT Group 4 drawings
- `.tif` / `.tiff`
- `.png`
- `.jpg` / `.jpeg`
- `.bmp`
- `.gif`
- `.webp`
- `.pbm` / `.pgm` / `.ppm`

PDF preview is optional if `pymupdf` is installed. PDF files are not batch converted because they are already PDFs.

## Install

```bat
py -m pip install -r requirements.txt
```

Optional PDF preview support:

```bat
py -m pip install pymupdf
```

## Run

```bat
py c4_pdf_dashboard.py
```

Or double click:

```text
run_c4_pdf_dashboard.bat
```

## Batch convert a folder tree

1. Open the dashboard.
2. Click **Batch convert folder...**.
3. Pick the top folder.
4. The program searches all subfolders for supported files.
5. It writes each output PDF in the same folder as the source file.

Example:

```text
C:\Drawings\JobA\8213899-17-M191F672M1.C4
C:\Drawings\JobA\8213899-17-M191F672M1.pdf
```

To replace existing PDFs, check **Overwrite PDFs in batch** before starting batch conversion.

## C4 decoding notes

This tool decodes the common JEDMICS/C4 layout used by tiled black and white engineering raster drawings:

- 512 x 512 tiles
- CCITT Group 4 compression
- Little endian tile index sizes
- Drawing scale defaults to 200 DPI

The DPI value can be changed in the dashboard before saving or batch converting.
