/*
  Browser folder batch conversion for C4/MIL files.

  The browser cannot silently write PDFs back into the selected source folders.
  Instead this scans the selected directory tree locally, converts supported files,
  preserves relative paths inside a ZIP archive, and downloads that ZIP.
*/

(() => {
  const DEFAULT_DPI = 200;
  const SUPPORTED_EXTENSIONS = [".c4", ".mil"];

  function getExportedConverter() {
    const exported = window.module && window.module.exports ? window.module.exports : {};
    if (typeof exported.parseC4 !== "function" || typeof exported.buildPdfFromC4 !== "function") {
      throw new Error("Could not find the C4 parser exported by app.js.");
    }
    return exported;
  }

  function isSupportedFile(file) {
    const name = (file && file.name ? file.name : "").toLowerCase();
    return SUPPORTED_EXTENSIONS.some((ext) => name.endsWith(ext));
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

  function waitForPaint() {
    return new Promise((resolve) => setTimeout(resolve, 0));
  }

  function downloadBytes(bytes, fileName, mimeType) {
    const blob = new Blob([bytes], { type: mimeType });
    const url = URL.createObjectURL(blob);
    try {
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }
  }

  function stripTopFolder(relativePath) {
    const normalized = relativePath.replace(/\\/g, "/");
    const parts = normalized.split("/").filter(Boolean);
    if (parts.length <= 1) return normalized;
    return parts.slice(1).join("/");
  }

  function pdfPathForFile(file) {
    const relativePath = file.webkitRelativePath ? stripTopFolder(file.webkitRelativePath) : file.name;
    return relativePath.replace(/\.[^/.]+$/, ".pdf");
  }

  const crcTable = (() => {
    const table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      table[i] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) {
      c = crcTable[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  function dosDateTime(date = new Date()) {
    const year = Math.max(1980, date.getFullYear());
    const dosTime =
      (date.getHours() << 11) |
      (date.getMinutes() << 5) |
      Math.floor(date.getSeconds() / 2);
    const dosDate =
      ((year - 1980) << 9) |
      ((date.getMonth() + 1) << 5) |
      date.getDate();
    return { dosTime, dosDate };
  }

  function utf8(text) {
    return new TextEncoder().encode(text);
  }

  function concat(chunks) {
    let total = 0;
    for (const chunk of chunks) total += chunk.length;
    const out = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      out.set(chunk, offset);
      offset += chunk.length;
    }
    return out;
  }

  function pushU16(out, value) {
    out.push(value & 0xff, (value >>> 8) & 0xff);
  }

  function pushU32(out, value) {
    out.push(value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff);
  }

  function makeZip(entries) {
    const localChunks = [];
    const centralChunks = [];
    let offset = 0;
    const timestamp = dosDateTime();

    for (const entry of entries) {
      const nameBytes = utf8(entry.path);
      const data = entry.data;
      const checksum = crc32(data);

      const localHeader = [];
      pushU32(localHeader, 0x04034b50);
      pushU16(localHeader, 20);
      pushU16(localHeader, 0x0800);
      pushU16(localHeader, 0);
      pushU16(localHeader, timestamp.dosTime);
      pushU16(localHeader, timestamp.dosDate);
      pushU32(localHeader, checksum);
      pushU32(localHeader, data.length);
      pushU32(localHeader, data.length);
      pushU16(localHeader, nameBytes.length);
      pushU16(localHeader, 0);

      const localHeaderBytes = new Uint8Array(localHeader);
      localChunks.push(localHeaderBytes, nameBytes, data);

      const centralHeader = [];
      pushU32(centralHeader, 0x02014b50);
      pushU16(centralHeader, 20);
      pushU16(centralHeader, 20);
      pushU16(centralHeader, 0x0800);
      pushU16(centralHeader, 0);
      pushU16(centralHeader, timestamp.dosTime);
      pushU16(centralHeader, timestamp.dosDate);
      pushU32(centralHeader, checksum);
      pushU32(centralHeader, data.length);
      pushU32(centralHeader, data.length);
      pushU16(centralHeader, nameBytes.length);
      pushU16(centralHeader, 0);
      pushU16(centralHeader, 0);
      pushU16(centralHeader, 0);
      pushU16(centralHeader, 0);
      pushU32(centralHeader, 0);
      pushU32(centralHeader, offset);

      centralChunks.push(new Uint8Array(centralHeader), nameBytes);
      offset += localHeaderBytes.length + nameBytes.length + data.length;
    }

    const centralDirectory = concat(centralChunks);
    const centralOffset = offset;
    const end = [];
    pushU32(end, 0x06054b50);
    pushU16(end, 0);
    pushU16(end, 0);
    pushU16(end, entries.length);
    pushU16(end, entries.length);
    pushU32(end, centralDirectory.length);
    pushU32(end, centralOffset);
    pushU16(end, 0);

    return concat([...localChunks, centralDirectory, new Uint8Array(end)]);
  }

  async function convertFolderFiles(fileList) {
    const files = Array.from(fileList || []);
    const supported = files.filter(isSupportedFile).sort((a, b) => {
      const ap = a.webkitRelativePath || a.name;
      const bp = b.webkitRelativePath || b.name;
      return ap.localeCompare(bp);
    });

    if (!supported.length) {
      setStatus("No .C4 or .MIL files were found in that folder.", true);
      setDetails(`Scanned ${files.length.toLocaleString()} file(s), but found no supported C4/MIL drawings.`);
      return;
    }

    const { parseC4, buildPdfFromC4 } = getExportedConverter();
    const dpi = getDpi();
    const zipEntries = [];
    const report = [];
    let converted = 0;
    let failed = 0;

    setStatus(`Found ${supported.length.toLocaleString()} C4/MIL file(s). Converting...`);
    setDetails("");
    await waitForPaint();

    for (let i = 0; i < supported.length; i++) {
      const file = supported[i];
      const inputPath = file.webkitRelativePath || file.name;
      const outputPath = pdfPathForFile(file);
      setStatus(`Converting ${i + 1} of ${supported.length}: ${inputPath}`);

      try {
        const buffer = await file.arrayBuffer();
        const parsed = parseC4(buffer);
        const pdfBytes = buildPdfFromC4(parsed, dpi);
        zipEntries.push({ path: outputPath, data: pdfBytes });
        converted++;
        report.push(`OK   ${inputPath} -> ${outputPath} (${parsed.width} x ${parsed.height}, ${parsed.tileCount} tiles)`);
      } catch (error) {
        failed++;
        const message = error instanceof Error ? error.message : String(error);
        report.push(`FAIL ${inputPath} -> ${message}`);
      }

      if (i % 5 === 0) {
        setDetails(report.slice(-30).join("\n"));
        await waitForPaint();
      }
    }

    report.unshift(
      "C4/MIL folder batch conversion report",
      `Generated: ${new Date().toLocaleString()}`,
      `DPI: ${dpi}`,
      `Scanned files: ${files.length}`,
      `Supported C4/MIL files: ${supported.length}`,
      `Converted: ${converted}`,
      `Failed: ${failed}`,
      ""
    );
    zipEntries.push({ path: "conversion_report.txt", data: utf8(report.join("\n")) });

    if (!converted) {
      setStatus("No PDFs were created. See the conversion report below.", true);
      setDetails(report.join("\n"));
      return;
    }

    setStatus("Building ZIP download...");
    await waitForPaint();
    const zipBytes = makeZip(zipEntries);
    downloadBytes(zipBytes, "c4-mil-converted-pdfs.zip", "application/zip");

    setStatus(`Batch complete. Converted ${converted} file(s)${failed ? `, ${failed} failed` : ""}. ZIP download started.`);
    setDetails(report.join("\n"));
  }

  function setupFolderBatch() {
    const folderInput = document.getElementById("folderInput");
    const folderButton = document.getElementById("folderButton");
    if (!folderInput || !folderButton) return;

    if (!("webkitdirectory" in folderInput)) {
      folderButton.disabled = true;
      folderButton.title = "This browser does not expose folder selection to web pages.";
      return;
    }

    folderButton.addEventListener("click", () => {
      folderInput.value = "";
      folderInput.click();
    });

    folderInput.addEventListener("change", () => convertFolderFiles(folderInput.files));
  }

  document.addEventListener("DOMContentLoaded", setupFolderBatch);
})();
