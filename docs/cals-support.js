/* CALS Type 1 raster support. CAL/CALS files are converted without uploading. */
(() => {
  const DEFAULT_DPI = 300;
  const CALS_HEADER_SIZE = 2048;
  const TILE_SIZE = 512;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder("ascii");

  class CalsError extends Error {}

  function ascii(text) {
    return encoder.encode(text);
  }

  function concat(chunks) {
    let size = 0;
    for (const chunk of chunks) size += chunk.length;
    const out = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      out.set(chunk, offset);
      offset += chunk.length;
    }
    return out;
  }

  function isCalsName(name) {
    const lower = String(name || "").toLowerCase();
    return lower.endsWith(".cal") || lower.endsWith(".cals");
  }

  function isC4MilName(name) {
    const lower = String(name || "").toLowerCase();
    return lower.endsWith(".c4") || lower.endsWith(".mil");
  }

  function isSupportedDrawingName(name) {
    return isC4MilName(name) || isCalsName(name);
  }

  function parseCalsHeader(bytes) {
    if (bytes.length <= CALS_HEADER_SIZE) {
      throw new CalsError("File is too small to contain a CALS Type 1 header and image data.");
    }
    const fields = {};
    for (let offset = 0; offset < CALS_HEADER_SIZE; offset += 128) {
      const record = decoder.decode(bytes.slice(offset, offset + 128)).trim();
      const colon = record.indexOf(":");
      if (colon < 0) continue;
      const key = record.slice(0, colon).trim().toLowerCase();
      const value = record.slice(colon + 1).trim();
      if (key) fields[key] = value;
    }
    return fields;
  }

  function parseCals(arrayBuffer) {
    if (!(arrayBuffer instanceof ArrayBuffer)) {
      throw new CalsError("CALS parser expected an ArrayBuffer.");
    }
    const bytes = new Uint8Array(arrayBuffer);
    const fields = parseCalsHeader(bytes);
    const rtype = String(fields.rtype || "").trim();
    if (!["1", "01", "001"].includes(rtype)) {
      throw new CalsError(`Unsupported or missing CALS rtype: ${rtype || "(missing)"}.`);
    }

    const rpelcnt = String(fields.rpelcnt || "").replace(/\s+/g, "");
    const match = rpelcnt.match(/^(\d+),(\d+)$/);
    if (!match) {
      throw new CalsError(`Could not parse CALS rpelcnt field: ${fields.rpelcnt || "(missing)"}.`);
    }

    const width = Number.parseInt(match[1], 10);
    const height = Number.parseInt(match[2], 10);
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      throw new CalsError(`Invalid CALS dimensions: ${width} x ${height}.`);
    }

    const density = Number.parseInt(String(fields.rdensty || ""), 10);
    const dpi = Number.isFinite(density) && density > 0 ? density : DEFAULT_DPI;
    const data = bytes.slice(CALS_HEADER_SIZE);
    if (!data.length) throw new CalsError("CALS file has no image data after the 2048 byte header.");

    return {
      kind: "cals",
      format: "CALS Type 1 raster",
      compression: "CCITT Group 4",
      width,
      height,
      dpi,
      headerSize: CALS_HEADER_SIZE,
      fields,
      rorient: fields.rorient || "",
      data,
    };
  }

  function makeCalsImageObject(parsed) {
    return concat([
      ascii(
        `<< /Type /XObject /Subtype /Image /Width ${parsed.width} /Height ${parsed.height} ` +
          `/ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /CCITTFaxDecode ` +
          `/DecodeParms << /K -1 /Columns ${parsed.width} /Rows ${parsed.height} /BlackIs1 false >> ` +
          `/Length ${parsed.data.length} >>\nstream\n`
      ),
      parsed.data,
      ascii("\nendstream"),
    ]);
  }

  function makeC4ImageObject(tile) {
    const tileData = tile.data;
    if (tile.compression === 0x00) {
      return concat([
        ascii(
          `<< /Type /XObject /Subtype /Image /Width ${TILE_SIZE} /Height ${TILE_SIZE} ` +
            `/ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /CCITTFaxDecode ` +
            `/DecodeParms << /K -1 /Columns ${TILE_SIZE} /Rows ${TILE_SIZE} /BlackIs1 false >> ` +
            `/Length ${tileData.length} >>\nstream\n`
        ),
        tileData,
        ascii("\nendstream"),
      ]);
    }
    if (tile.compression === 0x80) {
      return concat([
        ascii(
          `<< /Type /XObject /Subtype /Image /Width ${TILE_SIZE} /Height ${TILE_SIZE} ` +
            `/ColorSpace /DeviceGray /BitsPerComponent 1 /Length ${tileData.length} >>\nstream\n`
        ),
        tileData,
        ascii("\nendstream"),
      ]);
    }
    throw new CalsError(`Unsupported C4 tile compression flag at tile ${tile.entryNo}.`);
  }

  function makePageObjectsForParsed(parsed, dpi, objects, nextObjectId) {
    const cleanDpi = Number.isFinite(dpi) && dpi > 0 ? dpi : (parsed.dpi || DEFAULT_DPI);
    const pageWidthPt = (parsed.width / cleanDpi) * 72;
    const pageHeightPt = (parsed.height / cleanDpi) * 72;
    const imageRefs = [];
    let content = "";

    if (parsed.kind === "cals") {
      const objectId = nextObjectId++;
      objects.set(objectId, makeCalsImageObject(parsed));
      imageRefs.push({ objectId });
      content = `q\n${pageWidthPt.toFixed(6)} 0 0 ${pageHeightPt.toFixed(6)} 0 0 cm\n/Im${objectId} Do\nQ\n`;
    } else {
      const tileWidthPt = (TILE_SIZE / cleanDpi) * 72;
      const tileHeightPt = (TILE_SIZE / cleanDpi) * 72;
      const sortedTiles = [...parsed.tiles].sort((a, b) => a.logicalTile - b.logicalTile);
      for (const tile of sortedTiles) {
        const objectId = nextObjectId++;
        objects.set(objectId, makeC4ImageObject(tile));
        imageRefs.push({ objectId, logicalTile: tile.logicalTile });
      }
      for (const ref of imageRefs) {
        const col = ref.logicalTile % parsed.cols;
        const row = Math.floor(ref.logicalTile / parsed.cols);
        const x = col * tileWidthPt;
        const y = pageHeightPt - (row + 1) * tileHeightPt;
        content += `q\n${tileWidthPt.toFixed(6)} 0 0 ${tileHeightPt.toFixed(6)} ${x.toFixed(6)} ${y.toFixed(6)} cm\n/Im${ref.objectId} Do\nQ\n`;
      }
    }

    const contentBytes = ascii(content);
    const contentObjectId = nextObjectId++;
    objects.set(contentObjectId, concat([ascii(`<< /Length ${contentBytes.length} >>\nstream\n`), contentBytes, ascii("endstream")]));

    const xobjects = imageRefs.map((ref) => `/Im${ref.objectId} ${ref.objectId} 0 R`).join(" ");
    const pageObjectId = nextObjectId++;
    objects.set(
      pageObjectId,
      ascii(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidthPt.toFixed(6)} ${pageHeightPt.toFixed(6)}] ` +
          `/Resources << /XObject << ${xobjects} >> >> /Contents ${contentObjectId} 0 R >>`
      )
    );

    return { pageObjectId, nextObjectId };
  }

  function buildPdfFromCals(parsed, dpi = parsed.dpi || DEFAULT_DPI) {
    return buildCombinedPdfFromParsedDocs([{ path: "cals", parsed }], dpi, "%PDF-1.4\n% CALS PDF generated by GitHub Pages\n");
  }

  function buildCombinedPdfFromParsedDocs(docs, dpi = DEFAULT_DPI, header = "%PDF-1.4\n% C4/MIL/CALS combined PDF generated by GitHub Pages\n") {
    if (!docs.length) throw new CalsError("No converted drawings are available to combine.");
    const objects = new Map();
    const pageIds = [];
    let nextObjectId = 3;

    for (const doc of docs) {
      const result = makePageObjectsForParsed(doc.parsed, dpi || doc.parsed.dpi || DEFAULT_DPI, objects, nextObjectId);
      nextObjectId = result.nextObjectId;
      pageIds.push(result.pageObjectId);
    }

    objects.set(2, ascii(`<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageIds.length} >>`));
    objects.set(1, ascii("<< /Type /Catalog /Pages 2 0 R >>"));

    const maxObjectId = Math.max(...objects.keys());
    const chunks = [ascii(header)];
    const offsets = new Array(maxObjectId + 1).fill(0);
    let length = chunks[0].length;
    for (let objectId = 1; objectId <= maxObjectId; objectId++) {
      const body = objects.get(objectId);
      if (!body) throw new CalsError(`Internal PDF build error: missing object ${objectId}.`);
      offsets[objectId] = length;
      const prefix = ascii(`${objectId} 0 obj\n`);
      const suffix = ascii("\nendobj\n");
      chunks.push(prefix, body, suffix);
      length += prefix.length + body.length + suffix.length;
    }

    const startXref = length;
    let xref = `xref\n0 ${maxObjectId + 1}\n0000000000 65535 f \n`;
    for (let objectId = 1; objectId <= maxObjectId; objectId++) {
      xref += `${String(offsets[objectId]).padStart(10, "0")} 00000 n \n`;
    }
    xref += `trailer\n<< /Size ${maxObjectId + 1} /Root 1 0 R >>\nstartxref\n${startXref}\n%%EOF\n`;
    chunks.push(ascii(xref));
    return concat(chunks);
  }

  function describeParsedDrawing(parsed) {
    if (parsed.kind === "cals") {
      const dpi = parsed.dpi || DEFAULT_DPI;
      return `${parsed.width} x ${parsed.height}, CALS Type 1, ${dpi} dpi`;
    }
    return `${parsed.width} x ${parsed.height}, ${parsed.tileCount} tiles`;
  }

  function convertDrawingArrayBuffer(arrayBuffer, name, dpi) {
    const exported = window.module && window.module.exports ? window.module.exports : {};
    if (isCalsName(name)) {
      const parsed = parseCals(arrayBuffer);
      return { parsed, pdfBytes: buildPdfFromCals(parsed, dpi || parsed.dpi || DEFAULT_DPI), kind: "CALS" };
    }
    if (isC4MilName(name)) {
      if (typeof exported.parseC4 !== "function" || typeof exported.buildPdfFromC4 !== "function") {
        throw new CalsError("Could not find the C4 parser exported by app.js.");
      }
      const parsed = exported.parseC4(arrayBuffer);
      parsed.kind = parsed.kind || "c4";
      return { parsed, pdfBytes: exported.buildPdfFromC4(parsed, dpi), kind: "C4/MIL" };
    }
    throw new CalsError(`Unsupported drawing extension: ${name}`);
  }

  function safePdfFileName(name) {
    const base = String(name || "converted").replace(/\.[^.]+$/, "") || "converted";
    return `${base}.pdf`;
  }

  function getDpi() {
    const input = document.getElementById("dpiInput");
    const value = Number.parseInt(input.value, 10);
    if (!Number.isFinite(value) || value < 72 || value > 600) {
      input.value = String(DEFAULT_DPI);
      return DEFAULT_DPI;
    }
    return value;
  }

  function setStatus(message, isError = false) {
    const status = document.getElementById("status");
    status.textContent = message;
    status.classList.toggle("error", isError);
  }

  function setDetails(message) {
    document.getElementById("details").textContent = message;
  }

  function setPreviewUrl(url) {
    document.getElementById("preview").src = url;
  }

  let calsPdfUrl = null;

  function clearCalsPdfUrl() {
    if (calsPdfUrl) URL.revokeObjectURL(calsPdfUrl);
    calsPdfUrl = null;
  }

  function describeCalsForUi(parsed, fileName, dpi) {
    const widthIn = parsed.width / dpi;
    const heightIn = parsed.height / dpi;
    return [
      `File: ${fileName}`,
      "Detected type: CALS Type 1 raster drawing",
      "Compression: CCITT Group 4",
      `Pixels: ${parsed.width.toLocaleString()} x ${parsed.height.toLocaleString()}`,
      `Header DPI: ${parsed.dpi}`,
      `PDF scale: ${dpi} dpi = ${widthIn.toFixed(2)} x ${heightIn.toFixed(2)} inches`,
      `Header bytes: ${parsed.headerSize}`,
      `Orientation field: ${parsed.rorient || "(blank)"}`,
      "PDF method: direct CCITT Group 4 image embedding",
      "Privacy: the file stays in this browser session.",
    ].join("\n");
  }

  async function convertCalsFile(file) {
    setStatus(`Reading ${file.name}...`);
    setDetails("");
    clearCalsPdfUrl();
    setPreviewUrl("about:blank");
    document.getElementById("downloadButton").disabled = true;
    document.getElementById("openButton").disabled = true;

    try {
      const dpi = getDpi();
      const parsed = parseCals(await file.arrayBuffer());
      const pdfBytes = buildPdfFromCals(parsed, dpi || parsed.dpi || DEFAULT_DPI);
      const blob = new Blob([pdfBytes], { type: "application/pdf" });
      calsPdfUrl = URL.createObjectURL(blob);
      const pdfFileName = safePdfFileName(file.name);

      const download = document.getElementById("downloadButton");
      download.disabled = false;
      download.onclick = () => {
        const a = document.createElement("a");
        a.href = calsPdfUrl;
        a.download = pdfFileName;
        document.body.appendChild(a);
        a.click();
        a.remove();
      };

      const open = document.getElementById("openButton");
      open.disabled = false;
      open.onclick = () => window.open(calsPdfUrl, "_blank", "noopener,noreferrer");

      setPreviewUrl(calsPdfUrl);
      setDetails(describeCalsForUi(parsed, file.name, dpi));
      setStatus(`Converted ${file.name} to ${pdfFileName}.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(message, true);
      setDetails("Conversion failed. This handler supports CALS Type 1 files with a 2048 byte header and CCITT Group 4 raster data.");
    }
  }

  function setupCalsSupport() {
    const fileInput = document.getElementById("fileInput");
    const multiFileInput = document.getElementById("multiFileInput");
    const dropZone = document.getElementById("dropZone");
    if (!fileInput || !dropZone) return;

    fileInput.setAttribute("accept", ".c4,.C4,.mil,.MIL,.cal,.CAL,.cals,.CALS");
    if (multiFileInput) multiFileInput.setAttribute("accept", ".c4,.C4,.mil,.MIL,.cal,.CAL,.cals,.CALS");

    fileInput.addEventListener(
      "change",
      (event) => {
        const file = fileInput.files && fileInput.files[0];
        if (!file || !isCalsName(file.name)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        convertCalsFile(file);
      },
      true
    );

    dropZone.addEventListener(
      "drop",
      (event) => {
        const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file || !isCalsName(file.name)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        dropZone.classList.remove("dragover");
        convertCalsFile(file);
      },
      true
    );

    setStatus("Ready. Select one .C4, .MIL, .CAL, or .CALS file.");
  }

  if (typeof window !== "undefined") {
    window.module = window.module || { exports: {} };
    Object.assign(window.module.exports, {
      CalsError,
      parseCals,
      buildPdfFromCals,
      buildCombinedPdfFromParsedDocs,
      convertDrawingArrayBuffer,
      describeParsedDrawing,
      isCalsName,
      isC4MilName,
      isSupportedDrawingName,
      supportedDrawingExtensions: [".c4", ".mil", ".cal", ".cals"],
    });
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", setupCalsSupport);
  }
})();
