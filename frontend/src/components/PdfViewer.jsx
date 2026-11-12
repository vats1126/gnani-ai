import React, { useState, useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { getSamplePdfBytes } from '../utils/samplePdf';

// Configure PDF.js worker using Vite's URL asset import
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024; // 15MB limit (Section 6 & 7C)

/**
 * Exports the currently rendered PDF canvas as a compressed JPEG data URL
 * with a solid white background (preventing transparent PDF layers from rendering black).
 */
function exportPdfPageSnapshot(sourceCanvas, maxDim = 1400, quality = 0.82) {
  if (!sourceCanvas || sourceCanvas.width === 0 || sourceCanvas.height === 0) {
    return null;
  }

  const srcW = sourceCanvas.width;
  const srcH = sourceCanvas.height;

  let dstW = srcW;
  let dstH = srcH;
  if (Math.max(srcW, srcH) > maxDim) {
    const scale = maxDim / Math.max(srcW, srcH);
    dstW = Math.round(srcW * scale);
    dstH = Math.round(srcH * scale);
  }

  const offscreen = document.createElement('canvas');
  offscreen.width = dstW;
  offscreen.height = dstH;
  const ctx = offscreen.getContext('2d');

  // Solid white paper background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, dstW, dstH);

  // Draw rendered page
  ctx.drawImage(sourceCanvas, 0, 0, dstW, dstH);

  const dataUrl = offscreen.toDataURL('image/jpeg', quality);
  const approxBytes = Math.round((dataUrl.length - 23) * 0.75);

  return {
    dataUrl,
    width: dstW,
    height: dstH,
    byteSize: approxBytes,
  };
}

const PdfViewer = forwardRef(function PdfViewer({
  onSnapshotGenerated,
  onClose,
  initialPdfData = null,
}, ref) {
  const [pdfDoc, setPdfDoc] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(1.15);
  const [fileName, setFileName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);
  const renderTaskRef = useRef(null);

  // Load a PDF document from an ArrayBuffer or Uint8Array
  const loadPdfData = useCallback(async (dataBuffer, name = 'document.pdf') => {
    setIsLoading(true);
    setErrorMsg(null);

    // Cancel any running render task
    if (renderTaskRef.current) {
      try {
        renderTaskRef.current.cancel();
      } catch {
        // Safe ignore
      }
      renderTaskRef.current = null;
    }

    try {
      const loadingTask = pdfjsLib.getDocument({
        data: dataBuffer,
        cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.5.438/cmaps/',
        cMapPacked: true,
      });

      const doc = await loadingTask.promise;
      setPdfDoc(doc);
      setNumPages(doc.numPages);
      setCurrentPage(1);
      setFileName(name);
      setIsLoading(false);
    } catch (err) {
      if (err.name !== 'RenderingCancelledException') {
        loggerError('PDF Load error:', err);
        setErrorMsg('Failed to load PDF document: ' + (err.message || 'Corrupted file'));
      }
      setIsLoading(false);
    }
  }, []);

  // Handle initial data if supplied
  useEffect(() => {
    if (initialPdfData) {
      loadPdfData(initialPdfData, 'sample_worksheet.pdf');
    }
  }, [initialPdfData, loadPdfData]);

  // Render active page onto canvas
  const renderPage = useCallback(async (pageNumber, doc, currentScale) => {
    if (!doc || !canvasRef.current) return;

    if (renderTaskRef.current) {
      try {
        renderTaskRef.current.cancel();
      } catch {
        // Safe ignore
      }
      renderTaskRef.current = null;
    }

    try {
      const page = await doc.getPage(pageNumber);
      const canvas = canvasRef.current;
      if (!canvas) return;

      const dpr = window.devicePixelRatio || 1;
      const viewport = page.getViewport({ scale: currentScale });

      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = Math.floor(viewport.width) + 'px';
      canvas.style.height = Math.floor(viewport.height) + 'px';

      const ctx = canvas.getContext('2d');
      // Fill solid white background
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const renderContext = {
        canvasContext: ctx,
        viewport,
        transform: [dpr, 0, 0, dpr, 0, 0],
      };

      const task = page.render(renderContext);
      renderTaskRef.current = task;
      await task.promise;
      renderTaskRef.current = null;

      // Automatically generate JPEG snapshot for AI visual awareness
      const snapshot = exportPdfPageSnapshot(canvas);
      if (snapshot && onSnapshotGenerated) {
        onSnapshotGenerated({
          ...snapshot,
          source: 'pdf',
          pageNum: pageNumber,
          totalPages: doc.numPages,
        });
      }
    } catch (err) {
      if (err.name !== 'RenderingCancelledException') {
        console.error('PDF page render error:', err);
      }
    }
  }, [onSnapshotGenerated]);

  // Re-render when doc, page, or scale changes
  useEffect(() => {
    if (pdfDoc) {
      renderPage(currentPage, pdfDoc, scale);
    }
  }, [pdfDoc, currentPage, scale, renderPage]);

  // File upload change handler
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Enforce 15MB file size limit
    if (file.size > MAX_FILE_SIZE_BYTES) {
      const mbSize = (file.size / (1024 * 1024)).toFixed(1);
      setErrorMsg(`PDF exceeds the 15MB limit (${mbSize} MB). Please choose a smaller document.`);
      e.target.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = async (event) => {
      const arrayBuffer = event.target?.result;
      if (arrayBuffer) {
        await loadPdfData(new Uint8Array(arrayBuffer), file.name);
      }
    };
    reader.onerror = () => {
      setErrorMsg('Failed to read file from disk.');
    };
    reader.readAsArrayBuffer(file);
    e.target.value = '';
  };

  // Drag and drop handlers
  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
        setErrorMsg('Please upload a valid PDF document (.pdf).');
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setErrorMsg('PDF exceeds the 15MB limit. Please upload a smaller document.');
        return;
      }
      const reader = new FileReader();
      reader.onload = async (event) => {
        const arrayBuffer = event.target?.result;
        if (arrayBuffer) {
          await loadPdfData(new Uint8Array(arrayBuffer), file.name);
        }
      };
      reader.readAsArrayBuffer(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  // Load sample worksheet preset
  const handleLoadSample = () => {
    const bytes = getSamplePdfBytes();
    loadPdfData(bytes, 'sample_math_worksheet.pdf');
  };

  // Imperative handle for parent to capture snapshot on demand
  useImperativeHandle(ref, () => ({
    captureSnapshot: () => {
      if (canvasRef.current) {
        return exportPdfPageSnapshot(canvasRef.current);
      }
      return null;
    },
    hasDocument: () => pdfDoc !== null,
    getPage: () => currentPage,
  }));

  const loggerError = (...args) => console.error(...args);

  return (
    <div className="pdf-viewer-root">
      {/* PDF Controls Header Bar */}
      <div className="pdf-toolbar">
        <div className="pdf-toolbar-left">
          <span className="pdf-badge-icon">📄</span>
          <span className="pdf-doc-title" title={fileName || 'No document loaded'}>
            {fileName ? (fileName.length > 24 ? fileName.substring(0, 22) + '...' : fileName) : 'PDF Worksheet'}
          </span>
          {numPages > 0 && (
            <span className="pdf-page-indicator">
              Page {currentPage} of {numPages}
            </span>
          )}
        </div>

        {/* Page & Zoom Navigation (44px+ tap targets) */}
        {numPages > 0 && (
          <div className="pdf-nav-controls">
            <button
              type="button"
              className="pdf-btn pdf-btn-nav"
              disabled={currentPage <= 1 || isLoading}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              title="Previous Page"
              aria-label="Previous Page"
            >
              ◀ Prev
            </button>
            <button
              type="button"
              className="pdf-btn pdf-btn-nav"
              disabled={currentPage >= numPages || isLoading}
              onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
              title="Next Page"
              aria-label="Next Page"
            >
              Next ▶
            </button>
            <div className="pdf-zoom-group">
              <button
                type="button"
                className="pdf-btn pdf-btn-icon"
                onClick={() => setScale((s) => Math.max(0.6, s - 0.15))}
                title="Zoom Out"
                aria-label="Zoom Out"
              >
                🔍−
              </button>
              <button
                type="button"
                className="pdf-btn pdf-btn-icon"
                onClick={() => setScale((s) => Math.min(2.5, s + 0.15))}
                title="Zoom In"
                aria-label="Zoom In"
              >
                🔍+
              </button>
              <button
                type="button"
                className="pdf-btn"
                onClick={() => setScale(1.15)}
                title="Reset Zoom"
                aria-label="Reset Zoom"
              >
                Fit
              </button>
            </div>
          </div>
        )}

        <div className="pdf-toolbar-right">
          <button
            type="button"
            className="pdf-btn pdf-btn-upload"
            onClick={() => fileInputRef.current?.click()}
            title="Upload a new PDF file (max 15MB)"
          >
            📤 Upload PDF
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          {onClose && (
            <button
              type="button"
              className="pdf-btn pdf-btn-close"
              onClick={onClose}
              title="Return to Whiteboard"
              aria-label="Close PDF and back to whiteboard"
            >
              ✏️ Back to Board
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {errorMsg && (
        <div className="pdf-error-banner" role="alert">
          <span>⚠️ {errorMsg}</span>
          <button type="button" className="pdf-error-close" onClick={() => setErrorMsg(null)}>✕</button>
        </div>
      )}

      {/* Main View Area */}
      <div className="pdf-canvas-container" onDrop={handleDrop} onDragOver={handleDragOver}>
        {isLoading && (
          <div className="pdf-loading-overlay">
            <div className="pdf-spinner" />
            <span>Loading PDF document...</span>
          </div>
        )}

        {!pdfDoc && !isLoading ? (
          <div className="pdf-empty-upload-box">
            <div className="pdf-upload-icon">📄</div>
            <h3 className="pdf-upload-title">Upload a PDF Worksheet</h3>
            <p className="pdf-upload-subtitle">
              Drag and drop any school textbook chapter, exam paper, or assignment PDF here.
            </p>
            <div className="pdf-upload-actions">
              <button
                type="button"
                className="btn-primary-upload"
                onClick={() => fileInputRef.current?.click()}
              >
                📁 Browse PDF from Device
              </button>
              <button
                type="button"
                className="btn-sample-worksheet"
                onClick={handleLoadSample}
              >
                ⚡ Load Sample Math Worksheet
              </button>
            </div>
            <span className="pdf-size-hint">Maximum file size: 15 MB &bull; Rendered locally in browser</span>
          </div>
        ) : (
          <div className="pdf-canvas-wrapper">
            <canvas ref={canvasRef} className="pdf-page-canvas" />
          </div>
        )}
      </div>
    </div>
  );
});

export default PdfViewer;

