/* Browser folder and multi-file batch conversion for C4/MIL/CALS drawings. */
(() => {
  const DEFAULT_DPI = 200;

  function getExportedConverter() {
    const exported = window.module && window.module.exports ? window.module.exports : {};
    if (typeof exported.convertDrawingArrayBuffer !== "function" || typeof exported.buildCombinedPdfFromParsedDocs !== "function") {
      throw new Error("Could not find the drawing converter exported by app.js/cals-support.js.");
    }
    return exported;
  }

  function isSupportedFile(file) {
    const exported = getExportedConverter();
    return exported.isSupportedDrawingName(file && file.name ? file.name : "");
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

  function shouldCombineIntoOnePdf() {
    const checkbox = document.getElementById("combinePdfCheckbox");
    return Boolean(checkbox && checkbox.checked);
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

  function relativePathForFile(file) {
    return file.webkitRelativePath ? stripTopFolder(file.webkitRelativePath) : file.name;
  }

  function pdfPathForFile(file) {
    return relativePathForFile(file).replace(/\.[^/.]+$/, ".pdf");
  }

  function makeUniquePath(path, usedPaths) {
    const normalized = path.replace(/\\/g, "/");
    if (!usedPaths.has(normalized)) {
      usedPaths.add(normalized);
      return normalized;
    }
    const dot = normalized.lastIndexOf(".");
    const slash = normalized.lastIndexOf("/");
    const hasExtension = dot > slash;
    const stem = hasExtension ? normalized.slice(0, dot) : normalized;
    const extension = hasExtension ? normalized.slice(dot) : "";
    let counter = 2;
    while (true) {
      const candidate = `${stem}_${counter}${extension}`;
      if (!usedPaths.has(candidate)) {
        usedPaths.add(candidate);
        return candidate;
      }
      counter++;
    }
  }

  const crcTable = (() => {
    const table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[i] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = crcTable[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  function dosDateTime(date = new Date()) {
    const year = Math.max(1980, date.getFullYear());
    return {
      dosTime: (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2),
      dosDate: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    };
  }

  function utf8(text) { return new TextEncoder().encode(text); }

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

  function pushU16(out, value) { out.push(value & 0xff, (value >>> 8) & 0xff); }
  function pushU32(out, value) { out.push(value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff); }

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
      pushU32(localHeader, 0x04034b50); pushU16(localHeader, 20); pushU16(localHeader, 0x0800); pushU16(localHeader, 0);
      pushU16(localHeader, timestamp.dosTime); pushU16(localHeader, timestamp.dosDate);
      pushU32(localHeader, checksum); pushU32(localHeader, data.length); pushU32(localHeader, data.length);
      pushU16(localHeader, nameBytes.length); pushU16(localHeader, 0);
      const localHeaderBytes = new Uint8Array(localHeader);
      localChunks.push(localHeaderBytes, nameBytes, data);

      const centralHeader = [];
      pushU32(centralHeader, 0x02014b50); pushU16(centralHeader, 20); pushU16(centralHeader, 20); pushU16(centralHeader, 0x0800); pushU16(centralHeader, 0);
      pushU16(centralHeader, timestamp.dosTime); pushU16(centralHeader, timestamp.dosDate);
      pushU32(centralHeader, checksum); pushU32(centralHeader, data.length); pushU32(centralHeader, data.length);
      pushU16(centralHeader, nameBytes.length); pushU16(centralHeader, 0); pushU16(centralHeader, 0); pushU16(centralHeader, 0); pushU16(centralHeader, 0);
      pushU32(centralHeader, 0); pushU32(centralHeader, offset);
      centralChunks.push(new Uint8Array(centralHeader), nameBytes);
      offset += localHeaderBytes.length + nameBytes.length + data.length;
    }
    const centralDirectory = concat(centralChunks);
    const end = [];
    pushU32(end, 0x06054b50); pushU16(end, 0); pushU16(end, 0); pushU16(end, entries.length); pushU16(end, entries.length);
    pushU32(end, centralDirectory.length); pushU32(end, offset); pushU16(end, 0);
    return concat([...localChunks, centralDirectory, new Uint8Array(end)]);
  }

  async function collectConvertedDocs(supported, exported, dpi) {
    const zipEntries = [];
    const combinedDocs = [];
    const report = [];
    const usedOutputPaths = new Set();
    let converted = 0;
    let failed = 0;

    for (let i = 0; i < supported.length; i++) {
      const file = supported[i];
      const inputPath = file.webkitRelativePath || file.name;
      const outputPath = makeUniquePath(pdfPathForFile(file), usedOutputPaths);
      setStatus(`Converting ${i + 1} of ${supported.length}: ${inputPath}`);
      try {
        const result = exported.convertDrawingArrayBuffer(await file.arrayBuffer(), file.name, dpi);
        zipEntries.push({ path: outputPath, data: result.pdfBytes });
        combinedDocs.push({ path: inputPath, outputPath, parsed: result.parsed });
        converted++;
        report.push(`OK   ${inputPath} -> ${outputPath} (${exported.describeParsedDrawing(result.parsed)})`);
      } catch (error) {
        failed++;
        report.push(`FAIL ${inputPath} -> ${error instanceof Error ? error.message : String(error)}`);
      }
      if (i % 5 === 0) {
        setDetails(report.slice(-30).join("\n"));
        await waitForPaint();
      }
    }
    return { zipEntries, combinedDocs, report, converted, failed };
  }

  function buildReportHeader(mode, files, supported, converted, failed, dpi) {
    return [
      `C4/MIL/CALS ${mode} conversion report`,
      `Generated: ${new Date().toLocaleString()}`,
      `DPI: ${dpi}`,
      `Scanned files: ${files.length}`,
      `Supported drawing files: ${supported.length}`,
      `Converted: ${converted}`,
      `Failed: ${failed}`,
      "",
    ];
  }

  async function convertBatchFiles(fileList, sourceLabel) {
    const exported = getExportedConverter();
    const files = Array.from(fileList || []);
    const supported = files.filter((file) => exported.isSupportedDrawingName(file.name)).sort((a, b) => {
      const ap = a.webkitRelativePath || a.name;
      const bp = b.webkitRelativePath || b.name;
      return ap.localeCompare(bp);
    });

    if (!supported.length) {
      setStatus(`No .C4, .MIL, .CAL, or .CALS files were found in the selected ${sourceLabel}.`, true);
      setDetails(`Scanned ${files.length.toLocaleString()} file(s), but found no supported drawings.`);
      return;
    }

    const dpi = getDpi();
    const combine = shouldCombineIntoOnePdf();
    setStatus(`Found ${supported.length.toLocaleString()} drawing file(s). Converting${combine ? " into one PDF" : ""}...`);
    setDetails("");
    await waitForPaint();

    const result = await collectConvertedDocs(supported, exported, dpi);
    const fullReport = [
      ...buildReportHeader(combine ? "combined PDF" : "folder/file batch", files, supported, result.converted, result.failed, dpi),
      ...result.report,
    ];

    if (!result.converted) {
      setStatus("No PDFs were created. See the conversion report below.", true);
      setDetails(fullReport.join("\n"));
      return;
    }

    if (combine) {
      setStatus("Building combined PDF download...");
      await waitForPaint();
      const combinedPdfBytes = exported.buildCombinedPdfFromParsedDocs(result.combinedDocs, dpi);
      downloadBytes(combinedPdfBytes, "c4-mil-cals-combined.pdf", "application/pdf");
      setStatus(`Combined PDF complete. Added ${result.converted} page(s)${result.failed ? `, ${result.failed} failed` : ""}. Download started.`);
      setDetails([...fullReport, "", "Combined PDF page order:", ...result.combinedDocs.map((doc, index) => `${index + 1}. ${doc.path}`)].join("\n"));
      return;
    }

    const zipBytes = makeZip([...result.zipEntries, { path: "conversion_report.txt", data: utf8(fullReport.join("\n")) }]);
    downloadBytes(zipBytes, "c4-mil-cals-converted-pdfs.zip", "application/zip");
    setStatus(`Batch complete. Converted ${result.converted} file(s)${result.failed ? `, ${result.failed} failed` : ""}. ZIP download started.`);
    setDetails(fullReport.join("\n"));
  }

  function setupBatchInputs() {
    const folderInput = document.getElementById("folderInput");
    const folderButton = document.getElementById("folderButton");
    const multiFileInput = document.getElementById("multiFileInput");
    const filesButton = document.getElementById("filesButton");

    if (folderInput && folderButton) {
      if (!("webkitdirectory" in folderInput)) {
        folderButton.disabled = true;
        folderButton.title = "This browser does not expose recursive folder selection to web pages. Use Choose drawing files instead.";
      } else {
        folderButton.addEventListener("click", () => { folderInput.value = ""; folderInput.click(); });
        folderInput.addEventListener("change", () => convertBatchFiles(folderInput.files, "folder"));
      }
    }

    if (multiFileInput && filesButton) {
      filesButton.addEventListener("click", () => { multiFileInput.value = ""; multiFileInput.click(); });
      multiFileInput.addEventListener("change", () => convertBatchFiles(multiFileInput.files, "file list"));
    }
  }

  document.addEventListener("DOMContentLoaded", setupBatchInputs);
})();
