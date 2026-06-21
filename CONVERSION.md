# How C4 and MIL to PDF Conversion Works

This project converts legacy JEDMICS C4 raster drawings to PDF. It also supports `.MIL` files when they contain the same C4 CCITT4 drawing data.

There are two conversion paths in this repository:

1. The local Python dashboard rebuilds the drawing as an image, previews it, and saves it as PDF.
2. The GitHub Pages version parses the same C4 structure and builds a PDF directly in the browser.

Both paths are based on the same core idea: a C4 file is not a normal bitmap file. It is a tiled black and white engineering drawing made from 512 by 512 pixel tiles.

## Reference documents

The conversion logic is based on the public JEDMICS reference material included with this project or used during development:

- `C4-Img-Spec 2.pdf`, JEDMICS C4 Compressed Image File Format Technical Specification, Version 1.0, April 2002.
- `3018_FileTypes.pdf`, JBR 3.0.18 Standard JEDMICS File Types, 11 September 2017.
- `JBR_3.0.22_RST-DLF_Format_Spec 2.pdf`, JBR 3.0.22 Index File RST Format Definition, 9 December 2021.
- `MIS_STD_52406C_IS 3.pdf`, AMCOM EDIS delivery and metadata requirements, 10 May 2017.

For AMCOM EDIS delivery package context and `INDEX.DLF` metadata details, see [EDIS_DELIVERY.md](EDIS_DELIVERY.md).

## What a C4 file is

A JEDMICS C4 file stores one black and white raster image. It does not store color or gray scale data.

The C4 image is divided into fixed size tiles:

```text
512 pixels wide x 512 pixels high
262,144 pixels per tile
32,768 bytes per raw 1 bit per pixel tile
```

Most tiles are compressed with CCITT Group 4, also called CCITT T.6. Each tile is compressed independently, so the converter can process one tile at a time and then place it back into the correct position in the final drawing.

The C4 specification says C4 is structurally similar to tiled TIFF and TG4. The compressed tile data is CCITT Group 4 in all of them, but the file headers and tile index structures are different. That is why a C4 file cannot be treated as a normal TIFF even though the tile compression is related.

## Why MIL is supported

The JEDMICS file type table lists the normal C4 entry as:

```text
File Type:      1
Extension:      C4
Source Flavor:  C4
Dest Flavor:    C4
Format Code:    RSTR
Comment:        JEDMICS CCITT4
```

The same file type table also lists:

```text
File Type:      466
Extension:      MIL
Source Flavor:  C4
Dest Flavor:    C4
Content Code:   NATIVE
Format Code:    RSTR
Comment:        JEDMICS CCITT4 saved with a .mil extension
```

Because of that, this project treats `.C4` and `.MIL` as the same drawing data layout. The extension changes, but the internal C4 tile structure is handled the same way.

## C4 file structure

A C4 file is organized in this order:

```text
C4 header
C4 tile index
Compressed image data
Optional preview tile index
Optional preview compressed image data
```

The converter uses the main header, main tile index, and main compressed image data. It does not need the optional preview because modern viewers can scale the full image directly.

The optional preview is a historical feature. The C4 specification limits it to either no preview data or exactly six preview tiles. The preview was intended for old hardware that could not scale the full drawing quickly.

## Header fields used by the converter

The first part of the file is the C4 header. The converter reads the fields needed to locate and rebuild the tiled image.

| Offset | Field | Byte order | Use |
|---:|---|---|---|
| 0 | Index offset | little endian uint32 | Location of the tile index. |
| 4 | Line height | little endian uint16 | Final image height in pixels. |
| 6 | Byte width | little endian uint16 | Final image width in bytes. Pixel width equals byte width times 8. |
| 8 | Data offset | big endian uint32 | Location of the compressed tile data. |
| 12 | Number of tiles | single byte | Tile count, or zero when it must be derived from the image size. |
| 14 | Preview index offset | little endian uint32 | Optional preview tile index location. Not needed for normal conversion. |
| 18 | Preview height | little endian uint16 | Optional preview height. Not needed for normal conversion. |
| 20 | Preview width | little endian uint16 | Optional preview width in bytes. Not needed for normal conversion. |
| 22 | Preview data offset | big endian uint32 | Optional preview tile data location. Not needed for normal conversion. |
| 26 | Preview number of tiles | single byte | Either 0 or 6 according to the spec. |
| 36 | Format code | single byte | Usually 4 for images with 252 tiles or fewer, 6 for larger images. |

The converter computes:

```text
pixel_width = byte_width * 8
tile_columns = ceil(pixel_width / 512)
tile_rows = ceil(line_height / 512)
expected_tiles = tile_columns * tile_rows
```

If the header tile count is zero, the converter uses the expected tile count calculated from the image dimensions.

## Tile index entries

Each tile index entry is 4 bytes:

| Offset within entry | Field | Size | Meaning |
|---:|---|---:|---|
| 0 | Tile number | 1 byte | Logical tile position for smaller images. |
| 1 | Negative compression flag | 1 byte | Non zero means the tile is stored raw instead of compressed. |
| 2 | Data size | 2 bytes, little endian | Size of this tile payload in bytes. |

The tile payloads are stored sequentially starting at the data offset. The tile index gives the size of each tile payload, so the converter can walk through the tile data in order.

## Tile placement

Tiles are placed in row major order, meaning left to right across a row, then down to the next row.

For images with 252 tiles or fewer, the tile number field identifies the logical position of the tile. For larger images, the C4 specification says the tile number field is not meaningful and the entries must be interpreted in row major order.

The logical tile position becomes a column and row like this:

```text
column = logical_tile_number % tile_columns
row = floor(logical_tile_number / tile_columns)
```

The tile is placed at:

```text
x = column * 512
y = row * 512
```

After every tile is placed, the image is cropped back to the exact pixel width and height from the header. This matters because right edge and bottom edge tiles can contain padded unused space.

## Negative compression and raw tiles

The C4 spec allows a tile to be stored raw if compressing it would make it larger than the original 1 bit tile. That condition is called negative compression.

For a raw 512 by 512 tile, the tile payload should be:

```text
512 * 512 / 8 = 32,768 bytes
```

The specification says any non zero negative compression flag indicates a raw tile. The converter treats compressed and raw tile paths separately. Most real drawings are expected to use normal CCITT Group 4 compressed tiles.

## DPI and PDF size

C4 drawings are pixel based. The PDF page size is determined from the pixel size and selected DPI.

The C4 specification says that if the stored DPI value is invalid or greater than 400, software should assume 200 DPI. It also notes that legacy JEDMICS hard copy scanning hardware produced 200 DPI C4 images.

This project uses 200 DPI as the default. The user can change DPI before export.

The page size calculation is:

```text
page_width_inches = pixel_width / dpi
page_height_inches = pixel_height / dpi
page_width_points = page_width_inches * 72
page_height_points = page_height_inches * 72
```

PDF uses points, where 72 points equals 1 inch.

## Python desktop conversion path

The desktop dashboard uses Python, Tkinter, and Pillow.

The flow is:

```text
Select .C4 or .MIL file
Read bytes from disk
Parse C4 header
Validate offsets, image size, and tile count
Read tile index entries
Decode or load each tile
Paste each tile into a full size 1 bit image
Crop padded edge space
Preview the reconstructed drawing
Save the image as PDF at the selected DPI
```

For CCITT Group 4 compressed tiles, the Python code wraps each tile payload in a minimal temporary TIFF structure. Pillow can decode that TIFF wrapper because TIFF supports CCITT Group 4 compression. The wrapper is only used internally so Pillow can turn the tile stream into pixels.

For raw tiles, the Python path can load the 1 bit tile bytes directly when the tile uses the supported raw flag path.

The desktop path creates a full reconstructed image in memory. This is useful for preview, zoom, scroll, and batch conversion.

## Browser GitHub Pages conversion path

The browser version works differently.

It does not fully decode the CCITT Group 4 data into pixels. Instead, it builds a PDF that embeds the original compressed tile streams directly as PDF image objects.

The flow is:

```text
Select or drop one .C4 or .MIL file
Browser reads the file into memory
JavaScript parses the C4 header and tile index
JavaScript creates one PDF image object per tile
Each compressed tile is embedded with /CCITTFaxDecode
A PDF content stream places each tile at the correct location
The generated PDF is displayed in the browser preview
The user can open or download the PDF
```

For compressed tiles, the browser PDF uses:

```text
/Filter /CCITTFaxDecode
/DecodeParms << /K -1 /Columns 512 /Rows 512 /BlackIs1 false >>
```

`/K -1` tells the PDF viewer that the image stream is CCITT Group 4 data. The browser does not need to understand the image data itself; the PDF viewer renders it.

This is why the online converter can be fast and private. The file stays in the browser session, and the PDF is generated locally without uploading the drawing to a server.

## Difference between the two paths

| Area | Python dashboard | GitHub Pages converter |
|---|---|---|
| Input count | Single file and recursive batch folders | One file at a time |
| Preview method | Reconstructs pixels and previews in Tkinter | Generates PDF and previews the PDF |
| CCITT handling | Uses a minimal TIFF wrapper so Pillow can decode tiles | Embeds CCITT tile streams directly into PDF |
| Best use | Desktop workflow and bulk conversion | Quick one file conversion with no install |
| File privacy | Local desktop file access only | Local browser session only |

## Relationship to RST, DLF, and EDIS files

RST and DLF files are metadata index formats used by JEDMICS. They can describe document numbers, CAGE codes, revisions, sheet numbers, frame numbers, file names, file extensions, file paths, distribution statements, and file type values.

The RST/DLF specification says the `FileType` field must correspond to a value in the JEDMICS `FILE_TYPE_XREF` table. For C4, the important file type is `1`. The spec also says that when JEDMICS processes an IMAGE row with `FileType` value `1` and a file extension that is not `TIF`, the image is validated as a proper C4 image.

MIS-STD-52406C-IS provides AMCOM EDIS delivery context. It identifies `INDEX.DLF` as the root level pipe-delimited ASCII metadata file for an EDIS delivery package and defines fields such as `FileType`, `FileExtension`, `FileName`, and `FilePath`.

This converter does not currently parse RST or DLF metadata files. A future version could use RST or DLF to locate drawings and decide whether a referenced file should be passed through the C4/MIL conversion pipeline.

For more detail, see [EDIS_DELIVERY.md](EDIS_DELIVERY.md).

## What this converter is not

The JEDMICS file type table contains many other extensions. Most of them are CAD, vector, office document, electronics, archive, audio, video, or vendor native formats.

Those entries are registry mappings, not proof that the data is C4 image data.

This project should not claim to convert every JEDMICS file type. The correct scope is:

```text
Primary JEDMICS drawing support:
.C4 and .MIL C4/CCITT4 raster drawings

Additional desktop image support:
Pillow readable image formats such as TIFF, PNG, JPG, BMP, GIF, WEBP, PBM, PGM, and PPM
```

ZIP and TAR entries should be treated as containers. CAD and vector formats require specialized CAD software or separate conversion libraries.

## Validation checks

The converter performs basic structural checks before conversion:

- File must be large enough to contain a C4 header.
- Width and height must be greater than zero.
- Tile index offset must point inside the file.
- Tile data offset must point inside the file.
- Computed tile count must match the tile count from the header when the header provides one.
- Each tile index entry must fit inside the file.
- Each tile payload must fit inside the file.
- Unsupported tile compression flags fail with an error.

These checks catch many common cases where a file has the right extension but is not actually a supported C4/MIL drawing.

## Practical summary

A C4 or MIL drawing is converted by reading the header, finding every 512 by 512 tile, interpreting the tile index, and either decoding or embedding each CCITT Group 4 tile. The final PDF uses the selected DPI to turn pixels into real paper size.

The Python desktop version reconstructs the image first. The browser version writes a PDF directly from the tile streams.
