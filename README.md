# C4/MIL/CALS to PDF

Convert legacy C4/JEDMICS, MIL, CALS, and Group 4 TIFF engineering raster drawings to PDF.

![C4/MIL/CALS to PDF browser converter screenshot](Screenshot%202026-06-23%20170601.png)

This project now has two ways to use it:

1. **Online converter** through GitHub Pages for one-file conversion, browser folder/file batch conversion, ZIP/SFX package conversion, ZIP download, direct folder save on supported desktop browsers, or combined multi-page PDF output.
2. **Local Windows Python dashboard** for previewing, saving, batch converting folders directly beside source files, and batch extracting supported drawing/image files from ZIP or WinZip self extracting EXE delivery packages.

## Online converter

The online converter is up and running here:

[https://deerspotter.github.io/c4-mil-cals-to-pdf/](https://deerspotter.github.io/c4-mil-cals-to-pdf/)

Use this when you need a no-install browser converter for `.C4`, `.MIL`, `.CAL`, `.CALS`, `.TIF`, or `.TIFF` files.

The browser version runs locally in your browser. Selected files are not uploaded to a server. It reads the C4/JEDMICS tile data, CALS Type 1 CCITT Group 4 raster data, or supported TIFF CCITT Group 4 image data, builds PDF files in the browser, and lets you open/download a single generated PDF, download a ZIP from batch conversion, save a batch ZIP or combined PDF back into a selected folder when the browser supports folder write permission, combine batch output into one multi-page PDF, or read supported drawings from ZIP and WinZip self extracting `.EXE` delivery packages without executing the EXE.

Online converter features:

- Select or drag and drop one `.C4`, `.MIL`, `.CAL`, `.CALS`, `.TIF`, or `.TIFF` file.
- Preview the generated PDF in the browser.
- Change DPI before exporting.
- Open the generated PDF in a new tab.
- Download the generated PDF.
- Select a folder and scan subfolders for `.C4`, `.MIL`, `.CAL`, `.CALS`, `.TIF`, and `.TIFF` files when the browser supports recursive folder selection.
- Select multiple drawing files manually when folder selection is not available, such as on some iOS browsers.
- Select one or more `.ZIP` or WinZip self extracting `.EXE` packages and convert embedded `.C4` / `.MIL` / `.CAL` / `.CALS` / `.TIF` / `.TIFF` files.
- Download browser batch converted PDFs as one ZIP file with a conversion report.
- Use **Choose folder and save output there** on supported desktop browsers to write `c4-mil-cals-converted-pdfs.zip` directly into the selected source folder.
- Check **Combine batch output into one multi-page PDF** to download one combined PDF instead of a ZIP, or to save `c4-mil-cals-combined.pdf` into the selected folder when using the direct folder save button.
- No Python install required.

Browser TIFF note: browser TIFF support is intentionally narrow. It supports 1 bit CCITT Group 4 TIFF drawings, including multi-page TIFFs like many JEDMICS EDL exports. General color TIFFs, LZW TIFFs, JPEG compressed TIFFs, and multi-strip TIFF pages are not decoded in the browser.

Browser package note: `.EXE` support is for old WinZip self extracting archive delivery packages. The browser reads the file as bytes, locates the embedded ZIP directory, inflates supported drawing entries in memory, and never executes the EXE. Deflated package entries require a browser with `DecompressionStream("deflate-raw")` support, normally current desktop Chrome, Edge, or Firefox.

Browser folder batch note: normal web file pickers cannot silently write generated PDFs back into your original local folders. The direct save button uses browser folder write permission when available, usually in desktop Chromium based browsers. iOS Safari generally does not expose this direct folder write workflow, so use normal download or the Python dashboard when you need guaranteed local folder output.

## Local Python dashboard

The local dashboard is the full desktop version. Use this when you want folder batch conversion, recursive subfolder scanning, package extraction, or a Windows desktop preview workflow.

The launcher uses `c4_pdf_dashboard_mil.py`, which keeps the original `c4_pdf_dashboard.py` release code intact and adds `.MIL` support for JEDMICS CCITT4 files saved with a MIL extension, `.CAL` / `.CALS` support for CALS Type 1 CCITT Group 4 raster drawings, and multi-page `.TIF` / `.TIFF` PDF export.

The same launcher also supports ZIP and WinZip self extracting `.EXE` packages during batch conversion. Package EXEs are opened with Python's ZIP reader only. They are not executed. When a batch finds a package, output PDFs are written beside the package under a folder named `<package_name>_pdfs` while preserving the internal package folder structure.

## Documentation

For a technical explanation of the C4/MIL file structure, tile handling, PDF creation, and the difference between the Python and browser converters, see:

[CONVERSION.md](CONVERSION.md)

For CALS Type 1 `.CAL` / `.CALS` raster support, see:

[CALS_FORMAT.md](CALS_FORMAT.md)

For AMCOM EDIS delivery package context, `INDEX.DLF` metadata notes, and why `.C4` and `.MIL` are both treated as JEDMICS CCITT4 raster drawings, see:

[EDIS_DELIVERY.md](EDIS_DELIVERY.md)

For A-10 TMSS / JCALS OmniMark script package notes, legacy SGML publishing context, and `.c4` Teamcenter dataset evidence, see:

[TMSS_OMNIMARK_SCRIPTS.md](TMSS_OMNIMARK_SCRIPTS.md)

## Features

- Select a single C4/MIL/CALS/TIFF drawing or normal image file.
- Preview the decoded drawing on the right side with scroll and zoom.
- Save the selected drawing as a PDF.
- Batch convert a whole directory tree.
- Recursive batch mode searches all subfolders and writes each PDF beside the source file.
- Batch mode can expand ZIP and WinZip self extracting EXE packages and convert embedded C4/MIL/CALS/TIFF drawings and supported image files.
- Existing PDFs are skipped by default unless overwrite is enabled.

## Supported input formats

Direct conversion:

- `.C4` / `.c4` JEDMICS tiled CCITT Group 4 drawings
- `.MIL` / `.mil` JEDMICS CCITT4 drawings saved with a MIL extension
- `.CAL` / `.cal` CALS Type 1 CCITT Group 4 raster drawings
- `.CALS` / `.cals` CALS Type 1 CCITT Group 4 raster drawings
- `.tif` / `.tiff` images; browser support is limited to 1 bit CCITT Group 4 TIFF, while the Python dashboard uses Pillow for broader TIFF/image handling
- `.png`
- `.jpg` / `.jpeg`
- `.bmp`
- `.gif`
- `.webp`
- `.pbm` / `.pgm` / `.ppm`

Batch package extraction:

- `.zip` packages containing `.C4`, `.MIL`, `.CAL`, `.CALS`, `.TIF`, `.TIFF`, or other supported image files
- WinZip self extracting `.exe` packages containing `.C4`, `.MIL`, `.CAL`, `.CALS`, `.TIF`, `.TIFF`, or other supported image files

Old binary Word `.DOC` files may appear in some JEDMICS delivery packages as notes or native documents. They are listed as package contents by archive tools, but this converter does not convert `.DOC` files in the browser.

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
py c4_pdf_dashboard_mil.py
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
5. It writes each normal C4/MIL/CALS/TIFF/image output PDF in the same folder as the source file.
6. If it finds a ZIP or self extracting EXE package, it writes package outputs under `<package_name>_pdfs` beside that package.

To replace existing PDFs, check **Overwrite PDFs in batch** before starting batch conversion.

## C4/MIL decoding notes

This tool decodes the common JEDMICS/C4 layout used by tiled black and white engineering raster drawings. Some JEDMICS exports store the same C4/CCITT4 data with a `.MIL` extension, so this tool treats `.C4` and `.MIL` as the same drawing data layout.

- 512 x 512 tiles
- CCITT Group 4 compression
- Little endian tile index sizes
- Drawing scale defaults to 200 DPI
