# C4 Reader and Converter to PDF

Convert legacy C4/JEDMICS engineering raster drawings to PDF.

This project now has two ways to use it:

1. **Online one file converter** through GitHub Pages.
2. **Local Windows Python dashboard** for previewing, saving, and batch converting folders.

## Online converter

The online converter is up and running here:

[https://deerspotter.github.io/C4-Reader-and-Converter-to-pdf/](https://deerspotter.github.io/C4-Reader-and-Converter-to-pdf/)

Use this when you only need to convert one `.C4` file at a time.

The browser version runs locally in your browser. The selected file is not uploaded to a server. It reads the C4/JEDMICS tile data, builds a PDF in the browser, and lets you open or download the generated PDF.

Online converter features:

- Select or drag and drop one `.C4` file.
- Preview the generated PDF in the browser.
- Change DPI before exporting.
- Open the generated PDF in a new tab.
- Download the generated PDF.
- No Python install required.

## Local Python dashboard

The local dashboard is the full desktop version. Use this when you want folder batch conversion, recursive subfolder scanning, or a Windows desktop preview workflow.

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
