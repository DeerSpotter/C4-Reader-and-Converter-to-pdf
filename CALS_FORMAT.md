# CALS Type 1 Raster Support

This project supports `.CAL` and `.CALS` engineering raster drawings when they use the common CALS Type 1 layout.

## File layout

A supported CALS drawing has:

1. A 2048 byte ASCII header.
2. Header records stored as fixed 128 byte text records.
3. `rtype: 1`, identifying CALS Type 1 raster data.
4. `rpelcnt: <width>,<height>`, identifying the pixel dimensions.
5. `rdensty: <dpi>`, identifying the nominal drawing resolution when present.
6. Raw CCITT Group 4 compressed monochrome image data immediately after the 2048 byte header.

Example fields from a supported file:

```text
rtype: 1
rorient: 000,270
rpelcnt: 010200,006600
rdensty: 0300
```

That example becomes a 10,200 x 6,600 pixel drawing at 300 DPI, or 34 x 22 inches.

## How conversion works

The Python dashboard wraps the raw CCITT Group 4 strip in a minimal TIFF container so Pillow can decode it for preview and PDF export.

The browser converter does not decompress the raster. It writes a PDF image object that references the original CCITT Group 4 bytes directly through `/CCITTFaxDecode`.

## Supported extensions

- `.CAL`
- `.CALS`

Both extensions are handled the same way.

## Limitations

This support is for CALS Type 1 monochrome CCITT Group 4 raster drawings. It does not attempt to support unrelated `.cal` calendar files, non-Type-1 CALS variants, or proprietary application-specific CAL files.
