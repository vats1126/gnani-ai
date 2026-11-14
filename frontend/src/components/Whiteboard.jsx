import React, {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
  useImperativeHandle,
  forwardRef,
} from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import {
  normalizePoint,
  normalizeLineWidth,
  denormalizeLineWidth,
  renderPaperBackground,
  renderInkLayer,
  exportCompositeSnapshot,
  PAPER_STYLES,
  DEMO_PRESETS,
} from '../utils/canvas';
import { getSamplePdfBytes } from '../utils/samplePdf';
import WhiteboardToolbar from './WhiteboardToolbar';

// Safely configure PDF.js worker
try {
  if (pdfjsLib && pdfjsLib.GlobalWorkerOptions) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
  }
} catch (err) {
  console.warn('PDF.js worker initialization warning in Whiteboard:', err);
}

const Whiteboard = forwardRef(function Whiteboard(
  { onSnapshotGenerated, onDemoPresetLoaded, className = '' },
  ref
) {
  const containerRef = useRef(null);
  const stageRef = useRef(null);
  const bgCanvasRef = useRef(null);
  const inkCanvasRef = useRef(null);

  // Drawing state
  const [activeTool, setActiveTool] = useState('pen'); // 'pen' | 'highlighter' | 'text' | 'eraser'
  const [activeColor, setActiveColor] = useState('#1E293B');
  const [strokeWidth, setStrokeWidth] = useState(0.006); // Normalized ~4px
  const [paperStyle, setPaperStyle] = useState(PAPER_STYLES.MATH_GRID);

  // Active annotations on current page
  const [strokes, setStrokes] = useState([]);
  const [textAnnotations, setTextAnnotations] = useState([]);
  const [redoStack, setRedoStack] = useState([]);

  // Sanitized valid strokes: filters out any null, undefined, or malformed items
  const validStrokes = useMemo(() => {
    return Array.isArray(strokes)
      ? strokes.filter((s) => s && typeof s === 'object' && Array.isArray(s.points) && s.points.length > 0)
      : [];
  }, [strokes]);

  // Per-page annotation memory keyed by page: { board: {...}, page_1: {...}, page_2: {...} }
  const [annotationsByPage, setAnnotationsByPage] = useState({
    board: { strokes: [], textAnnotations: [], redoStack: [] },
  });

  // PDF state
  const [pdfDoc, setPdfDoc] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(1.15);
  const [fileName, setFileName] = useState('');
  const [isLoadingPdf, setIsLoadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState(null);
  const renderTaskRef = useRef(null);

  // Floating inline text / equation input state: { xPx, yPx, normX, normY, text }
  const [floatingTextInput, setFloatingTextInput] = useState(null);

  // Drawing tracking refs
  const isDrawingRef = useRef(false);
  const currentStrokeRef = useRef(null);
  const lastPointRef = useRef(null);

  // Snapshot toast preview state
  const [snapshotPreview, setSnapshotPreview] = useState(null);

  // Current page key helper
  const getCurrentKey = useCallback(() => {
    return pdfDoc ? `page_${currentPage}` : 'board';
  }, [pdfDoc, currentPage]);

  /**
   * Render Layer 0 (underlay: paper background or PDF page).
   */
  const renderLayer0 = useCallback(async () => {
    const bgCanvas = bgCanvasRef.current;
    if (!bgCanvas) return;

    const dpr = window.devicePixelRatio || 1;

    if (pdfDoc) {
      // Cancel previous PDF render task if still in progress
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {
          // Ignore cancellation errors
        }
        renderTaskRef.current = null;
      }

      try {
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale });

        const cssW = Math.floor(viewport.width);
        const cssH = Math.floor(viewport.height);

        bgCanvas.width = Math.floor(cssW * dpr);
        bgCanvas.height = Math.floor(cssH * dpr);
        bgCanvas.style.width = `${cssW}px`;
        bgCanvas.style.height = `${cssH}px`;

        if (inkCanvasRef.current) {
          inkCanvasRef.current.width = Math.floor(cssW * dpr);
          inkCanvasRef.current.height = Math.floor(cssH * dpr);
          inkCanvasRef.current.style.width = `${cssW}px`;
          inkCanvasRef.current.style.height = `${cssH}px`;
        }

        if (stageRef.current) {
          stageRef.current.style.width = `${cssW}px`;
          stageRef.current.style.height = `${cssH}px`;
        }

        const ctx = bgCanvas.getContext('2d');
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, bgCanvas.width, bgCanvas.height);

        const renderContext = {
          canvasContext: ctx,
          viewport,
          transform: [dpr, 0, 0, dpr, 0, 0],
        };

        const task = page.render(renderContext);
        renderTaskRef.current = task;
        await task.promise;
        renderTaskRef.current = null;
      } catch (err) {
        if (err?.name !== 'RenderingCancelledException') {
          console.warn('PDF page render error:', err);
        }
      }
    } else {
      // Blank Notebook mode
      const container = containerRef.current;
      const cssW = container ? container.clientWidth || 800 : 800;
      const cssH = container ? container.clientHeight || 600 : 600;

      if (stageRef.current) {
        stageRef.current.style.width = '100%';
        stageRef.current.style.height = '100%';
      }

      renderPaperBackground(bgCanvas, paperStyle, {
        customWidth: cssW,
        customHeight: cssH,
        dpr,
      });

      if (inkCanvasRef.current) {
        const targetW = Math.floor(cssW * dpr);
        const targetH = Math.floor(cssH * dpr);
        if (inkCanvasRef.current.width !== targetW || inkCanvasRef.current.height !== targetH) {
          inkCanvasRef.current.width = targetW;
          inkCanvasRef.current.height = targetH;
        }
        inkCanvasRef.current.style.width = '100%';
        inkCanvasRef.current.style.height = '100%';
      }
    }
  }, [pdfDoc, currentPage, scale, paperStyle]);

  /**
   * Render Layer 1 (ink & annotations overlay).
   */
  const renderLayer1 = useCallback(() => {
    const inkCanvas = inkCanvasRef.current;
    if (!inkCanvas) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = inkCanvas.clientWidth || 800;
    const cssH = inkCanvas.clientHeight || 600;

    renderInkLayer(inkCanvas, validStrokes, textAnnotations, {
      customWidth: cssW,
      customHeight: cssH,
      dpr,
      clear: true,
    });
  }, [validStrokes, textAnnotations]);

  // Redraw Layer 0 when paper style, PDF doc, page, or scale changes
  useEffect(() => {
    renderLayer0();
  }, [renderLayer0]);

  // Redraw Layer 1 when strokes or textAnnotations change
  useEffect(() => {
    renderLayer1();
  }, [renderLayer1]);

  /**
   * Handle responsive container resizing via ResizeObserver with loop guard.
   */
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let animId = null;
    let lastW = 0;
    let lastH = 0;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const cr = entry.contentRect;
        const w = Math.round(cr.width);
        const h = Math.round(cr.height);
        // Guard against duplicate / jitter notifications causing infinite loop
        if (w === lastW && h === lastH) continue;
        lastW = w;
        lastH = h;

        if (animId) cancelAnimationFrame(animId);
        animId = requestAnimationFrame(() => {
          renderLayer0();
          renderLayer1();
        });
      }
    });

    observer.observe(container);
    return () => {
      observer.disconnect();
      if (animId) cancelAnimationFrame(animId);
    };
  }, [renderLayer0, renderLayer1]);

  /**
   * PDF Document Loader.
   */
  const loadPdfData = useCallback(async (dataBuffer, name = 'worksheet.pdf') => {
    setIsLoadingPdf(true);
    setPdfError(null);

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
      setScale(1.15);
      setIsLoadingPdf(false);

      // Restore page 1 annotations if previously recorded
      const page1Data = annotationsByPage['page_1'] || { strokes: [], textAnnotations: [], redoStack: [] };
      const rawPage1Strokes = page1Data.strokes || [];
      const cleanPage1Strokes = Array.isArray(rawPage1Strokes)
        ? rawPage1Strokes.filter((s) => s && typeof s === 'object' && Array.isArray(s.points) && s.points.length > 0)
        : [];
      setStrokes(cleanPage1Strokes);
      setTextAnnotations(page1Data.textAnnotations || []);
      setRedoStack(page1Data.redoStack || []);
    } catch (err) {
      setIsLoadingPdf(false);
      setPdfError(err?.message || 'Failed to load PDF document');
      console.error('PDF load error:', err);
    }
  }, [annotationsByPage]);

  const loadSamplePdf = useCallback(async () => {
    const bytes = getSamplePdfBytes();
    await loadPdfData(bytes.buffer, 'sample_worksheet.pdf');
  }, [loadPdfData]);

  const loadPdfFile = useCallback(async (file) => {
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      alert('PDF file size exceeds 15MB limit.');
      return;
    }
    const reader = new FileReader();
    reader.onload = async (e) => {
      await loadPdfData(e.target.result, file.name);
    };
    reader.readAsArrayBuffer(file);
  }, [loadPdfData]);

  const closePdf = useCallback(() => {
    // Save current PDF page annotations
    if (pdfDoc) {
      const key = `page_${currentPage}`;
      setAnnotationsByPage((prev) => ({
        ...prev,
        [key]: { strokes: validStrokes, textAnnotations, redoStack },
      }));
    }

    // Restore blank board annotations
    const boardData = annotationsByPage['board'] || { strokes: [], textAnnotations: [], redoStack: [] };
    const rawBoardStrokes = boardData.strokes || [];
    const cleanBoardStrokes = Array.isArray(rawBoardStrokes)
      ? rawBoardStrokes.filter((s) => s && typeof s === 'object' && Array.isArray(s.points) && s.points.length > 0)
      : [];
    setStrokes(cleanBoardStrokes);
    setTextAnnotations(boardData.textAnnotations || []);
    setRedoStack(boardData.redoStack || []);

    if (renderTaskRef.current) {
      try {
        renderTaskRef.current.cancel();
      } catch {
        // Safe ignore
      }
      renderTaskRef.current = null;
    }

    if (pdfDoc) {
      try {
        pdfDoc.destroy();
      } catch {
        // Safe ignore
      }
    }

    setPdfDoc(null);
    setCurrentPage(1);
    setNumPages(0);
    setFileName('');
  }, [pdfDoc, currentPage, validStrokes, textAnnotations, redoStack, annotationsByPage]);

  /**
   * PDF Page Navigation with Per-Page Annotation Persistence.
   */
  const switchPage = useCallback((newPage) => {
    if (!pdfDoc || newPage < 1 || newPage > numPages || newPage === currentPage) return;

    // 1. Commit active page annotations
    const oldKey = `page_${currentPage}`;
    const newKey = `page_${newPage}`;

    setAnnotationsByPage((prev) => ({
      ...prev,
      [oldKey]: { strokes: validStrokes, textAnnotations, redoStack },
    }));

    // 2. Load target page annotations
    const targetData = annotationsByPage[newKey] || { strokes: [], textAnnotations: [], redoStack: [] };
    const rawTargetStrokes = targetData.strokes || [];
    const cleanTargetStrokes = Array.isArray(rawTargetStrokes)
      ? rawTargetStrokes.filter((s) => s && typeof s === 'object' && Array.isArray(s.points) && s.points.length > 0)
      : [];
    setStrokes(cleanTargetStrokes);
    setTextAnnotations(targetData.textAnnotations || []);
    setRedoStack(targetData.redoStack || []);

    // 3. Update current page
    setCurrentPage(newPage);
  }, [pdfDoc, currentPage, numPages, validStrokes, textAnnotations, redoStack, annotationsByPage]);

  /**
   * Composite Snapshot Export.
   */
  const exportSnapshot = useCallback(() => {
    const composite = exportCompositeSnapshot(bgCanvasRef.current, inkCanvasRef.current, {
      maxDim: 1400,
      quality: 0.85,
      hasPdf: Boolean(pdfDoc),
      pageNum: pdfDoc ? currentPage : 1,
      strokeCount: validStrokes.length + (textAnnotations || []).length,
    });

    if (onSnapshotGenerated) {
      onSnapshotGenerated(composite);
    }
    return composite;
  }, [pdfDoc, currentPage, validStrokes, textAnnotations, onSnapshotGenerated]);

  /**
   * Pointer Events: Live Spline Smoothing & Layer-Safe Drawing.
   */
  const getCanvasCoords = (e) => {
    const canvas = inkCanvasRef.current;
    if (!canvas) return { xPx: 0, yPx: 0, normX: 0, normY: 0, cssW: 1, cssH: 1 };
    const rect = canvas.getBoundingClientRect();
    const xPx = e.clientX - rect.left;
    const yPx = e.clientY - rect.top;
    const cssW = rect.width || 1;
    const cssH = rect.height || 1;
    const norm = normalizePoint(xPx, yPx, cssW, cssH);
    return { xPx, yPx, normX: norm.x, normY: norm.y, cssW, cssH };
  };

  const handlePointerDown = (e) => {
    if (e.button !== 0) return; // Left click only
    const canvas = inkCanvasRef.current;
    if (!canvas) return;

    const { xPx, yPx, normX, normY, cssW, cssH } = getCanvasCoords(e);

    // Text tool: open floating text / equation box
    if (activeTool === 'text') {
      setFloatingTextInput({
        xPx: Math.min(xPx, cssW - 180),
        yPx: Math.min(yPx, cssH - 40),
        normX,
        normY,
        text: '',
      });
      return;
    }

    // Dismiss floating text box if open
    if (floatingTextInput) {
      commitFloatingText();
    }

    isDrawingRef.current = true;
    try {
      canvas.setPointerCapture(e.pointerId);
    } catch {
      // Safe ignore
    }

    const t0 = Date.now();
    const p0 = { x: normX, y: normY };
    lastPointRef.current = { ...p0, t: t0 };

    currentStrokeRef.current = {
      tool: activeTool,
      color: activeColor,
      lineWidth: strokeWidth,
      points: [p0],
      timestamps: [t0],
    };

    // Draw initial dot feedback
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const baseWidth = denormalizeLineWidth(strokeWidth, cssW, cssH);
    if (activeTool === 'highlighter') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 0.35;
      ctx.fillStyle = activeColor || '#FACC15';
      ctx.beginPath();
      ctx.arc(xPx, yPx, (baseWidth * 2.8) / 2, 0, Math.PI * 2);
      ctx.fill();
    } else if (activeTool === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.globalAlpha = 1.0;
      ctx.beginPath();
      ctx.arc(xPx, yPx, (baseWidth * 2.5) / 2, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = activeColor || '#1E293B';
      ctx.beginPath();
      ctx.arc(xPx, yPx, baseWidth / 2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  };

  const handlePointerMove = (e) => {
    if (!isDrawingRef.current || !currentStrokeRef.current || !Array.isArray(currentStrokeRef.current.points)) return;
    const canvas = inkCanvasRef.current;
    if (!canvas) return;

    const { xPx, yPx, normX, normY, cssW, cssH } = getCanvasCoords(e);
    const last = lastPointRef.current;

    // Filter jitter
    if (last) {
      const dx = normX - last.x;
      const dy = normY - last.y;
      if (dx * dx + dy * dy < 0.000003) return;
    }

    const now = Date.now();
    const pCurrent = { x: normX, y: normY };
    currentStrokeRef.current.points.push(pCurrent);
    currentStrokeRef.current.timestamps.push(now);

    const pts = currentStrokeRef.current.points;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const baseWidth = denormalizeLineWidth(strokeWidth, cssW, cssH);

    // Dynamic velocity-aware width tapering for pen strokes
    let dynamicWidth = baseWidth;
    if (activeTool === 'pen' && last) {
      const distPx = Math.hypot((normX - last.x) * cssW, (normY - last.y) * cssH);
      const dt = Math.max(1, now - last.t);
      const vel = distPx / dt;
      const taper = Math.min(1, Math.max(0, vel / 3.0));
      dynamicWidth = baseWidth * (1 - 0.25 * taper);
    }

    if (activeTool === 'highlighter') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 0.35;
      ctx.strokeStyle = activeColor || '#FACC15';
      ctx.lineWidth = baseWidth * 2.8;
    } else if (activeTool === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = 'rgba(0,0,0,1)';
      ctx.lineWidth = baseWidth * 2.5;
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = activeColor || '#1E293B';
      ctx.lineWidth = dynamicWidth;
    }

    // Midpoint Quadratic Bezier Spline live rendering
    if (pts.length >= 3) {
      const pPrev2 = pts[pts.length - 3];
      const pPrev1 = pts[pts.length - 2];
      const pCurr = pts[pts.length - 1];

      const midPrevX = ((pPrev2.x + pPrev1.x) / 2) * cssW;
      const midPrevY = ((pPrev2.y + pPrev1.y) / 2) * cssH;
      const midNextX = ((pPrev1.x + pCurr.x) / 2) * cssW;
      const midNextY = ((pPrev1.y + pCurr.y) / 2) * cssH;

      ctx.beginPath();
      ctx.moveTo(midPrevX, midPrevY);
      ctx.quadraticCurveTo(pPrev1.x * cssW, pPrev1.y * cssH, midNextX, midNextY);
      ctx.stroke();
    } else if (pts.length === 2) {
      ctx.beginPath();
      ctx.moveTo(pts[0].x * cssW, pts[0].y * cssH);
      ctx.lineTo(pts[1].x * cssW, pts[1].y * cssH);
      ctx.stroke();
    }

    ctx.restore();
    lastPointRef.current = { ...pCurrent, t: now };
  };

  const endDrawing = (e) => {
    if (!isDrawingRef.current) return;
    isDrawingRef.current = false;

    const canvas = inkCanvasRef.current;
    if (canvas && e && e.pointerId) {
      try {
        canvas.releasePointerCapture(e.pointerId);
      } catch {
        // Safe ignore
      }
    }

    // Capture the completed stroke into a local const FIRST before clearing ref
    const completedStroke = currentStrokeRef.current
      ? {
          ...currentStrokeRef.current,
          points: Array.isArray(currentStrokeRef.current.points)
            ? [...currentStrokeRef.current.points]
            : [],
          timestamps: Array.isArray(currentStrokeRef.current.timestamps)
            ? [...currentStrokeRef.current.timestamps]
            : [],
        }
      : null;

    currentStrokeRef.current = null;
    lastPointRef.current = null;

    if (!completedStroke || !Array.isArray(completedStroke.points) || completedStroke.points.length === 0) {
      return;
    }

    // Pass completedStroke (NEVER currentStrokeRef.current) into state updater
    setStrokes((prev) => [
      ...(Array.isArray(prev) ? prev.filter((s) => s && Array.isArray(s.points) && s.points.length > 0) : []),
      completedStroke,
    ]);
    setRedoStack([]);
  };

  /**
   * Floating Text Annotation Handler.
   */
  const commitFloatingText = () => {
    if (!floatingTextInput) return;
    const text = floatingTextInput.text.trim();
    if (text) {
      const newAnnotation = {
        id: 'txt_' + Date.now(),
        text,
        x: floatingTextInput.normX,
        y: floatingTextInput.normY,
        color: activeColor,
        fontSizeNorm: 0.03,
      };
      setTextAnnotations((prev) => [...prev, newAnnotation]);
      setRedoStack([]);
    }
    setFloatingTextInput(null);
  };

  const cancelFloatingText = () => {
    setFloatingTextInput(null);
  };

  /**
   * Undo / Redo.
   */
  const handleUndo = useCallback(() => {
    if (validStrokes.length > 0) {
      const lastStroke = validStrokes[validStrokes.length - 1];
      setStrokes(validStrokes.slice(0, -1));
      setRedoStack((prev) => [{ type: 'stroke', item: lastStroke }, ...(Array.isArray(prev) ? prev : [])]);
    } else if (textAnnotations.length > 0) {
      const lastTxt = textAnnotations[textAnnotations.length - 1];
      setTextAnnotations((prev) => prev.slice(0, -1));
      setRedoStack((prev) => [{ type: 'text', item: lastTxt }, ...(Array.isArray(prev) ? prev : [])]);
    }
  }, [validStrokes, textAnnotations]);

  const handleRedo = useCallback(() => {
    if (redoStack.length === 0) return;
    const [action, ...remaining] = redoStack;
    setRedoStack(remaining);

    if (action.type === 'stroke' && action.item && Array.isArray(action.item.points) && action.item.points.length > 0) {
      setStrokes((prev) => [
        ...(Array.isArray(prev) ? prev.filter((s) => s && Array.isArray(s.points) && s.points.length > 0) : []),
        action.item,
      ]);
    } else if (action.type === 'text' && action.item) {
      setTextAnnotations((prev) => [...(Array.isArray(prev) ? prev.filter(Boolean) : []), action.item]);
    }
  }, [redoStack]);

  const handleClear = useCallback(() => {
    setStrokes([]);
    setTextAnnotations([]);
    setRedoStack([]);
    setFloatingTextInput(null);
  }, []);

  /**
   * Keyboard shortcuts: Cmd+Z (undo), Cmd+Shift+Z or Ctrl+Y (redo), Escape.
   */
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        cancelFloatingText();
        return;
      }
      const isCmdOrCtrl = e.metaKey || e.ctrlKey;
      if (!isCmdOrCtrl) return;

      if (e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
        e.preventDefault();
        handleRedo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleUndo, handleRedo]);

  /**
   * Test snapshot verification toast.
   */
  const handleTestSnapshot = () => {
    const snap = exportSnapshot();
    setSnapshotPreview(snap);
  };

  /**
   * Demo Presets Loader.
   */
  const handleSelectDemoPreset = (presetKey) => {
    const preset = DEMO_PRESETS[presetKey];
    if (!preset) return;

    if (pdfDoc) {
      closePdf();
    }

    if (preset.getStrokes) {
      const newStrokes = preset.getStrokes() || [];
      const cleanNewStrokes = Array.isArray(newStrokes)
        ? newStrokes.filter((s) => s && typeof s === 'object' && Array.isArray(s.points) && s.points.length > 0)
        : [];
      setStrokes(cleanNewStrokes);
      setTextAnnotations([]);
      setRedoStack([]);
    }

    if (onDemoPresetLoaded) {
      onDemoPresetLoaded(presetKey, preset);
    }
  };

  /**
   * Imperative API.
   */
  useImperativeHandle(ref, () => ({
    exportSnapshot,
    exportCompositeSnapshot: exportSnapshot,
    captureSnapshot: exportSnapshot,
    loadSamplePdf,
    loadPdfFile,
    loadPdf: loadPdfFile,
    closePdf,
    clear: handleClear,
    reset: handleClear,
    undo: handleUndo,
    redo: handleRedo,
    isEmpty: () => validStrokes.length === 0 && (textAnnotations || []).length === 0,
    getStrokeCount: () => validStrokes.length + (textAnnotations || []).length,
    hasPdf: () => Boolean(pdfDoc),
    getCurrentPage: () => (pdfDoc ? currentPage : 1),
    getNumPages: () => (pdfDoc ? numPages : 1),
    loadPreset: (key) => handleSelectDemoPreset(key),
  }));

  const isEmptyWorkspace = validStrokes.length === 0 && (textAnnotations || []).length === 0;

  return (
    <div className={`wb-container ${className}`} ref={containerRef}>
      {/* Universal Whiteboard & PDF Toolbar */}
      <WhiteboardToolbar
        activeTool={activeTool}
        setActiveTool={setActiveTool}
        activeColor={activeColor}
        setActiveColor={setActiveColor}
        strokeWidth={strokeWidth}
        setStrokeWidth={setStrokeWidth}
        canUndo={validStrokes.length > 0 || (textAnnotations || []).length > 0}
        canRedo={redoStack.length > 0}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onClear={handleClear}
        onTestSnapshot={handleTestSnapshot}
        onSelectDemoPreset={handleSelectDemoPreset}
        strokeCount={validStrokes.length + (textAnnotations || []).length}
        paperStyle={paperStyle}
        setPaperStyle={setPaperStyle}
        hasPdf={Boolean(pdfDoc)}
        currentPage={currentPage}
        numPages={numPages}
        onPrevPage={() => switchPage(currentPage - 1)}
        onNextPage={() => switchPage(currentPage + 1)}
        onZoomIn={() => setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)))}
        onZoomOut={() => setScale((s) => Math.max(0.7, +(s - 0.15).toFixed(2)))}
        onUploadPdf={loadPdfFile}
        onLoadSamplePdf={loadSamplePdf}
        onClosePdf={closePdf}
        pdfFileName={fileName}
      />

      {/* Canvas Stage Wrapper */}
      <div className="wb-canvas-wrapper" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <div ref={stageRef} className="wb-stage-container" style={{ position: 'relative', width: '100%', height: '100%' }}>
          {/* Layer 0: Background Paper Style or PDF Page */}
          <canvas
            ref={bgCanvasRef}
            className="wb-canvas wb-layer-bg"
            style={{ position: 'absolute', top: 0, left: 0, display: 'block' }}
          />

          {/* Layer 1: Smooth Ink, Highlighters, and Text Annotations */}
          <canvas
            ref={inkCanvasRef}
            className="wb-canvas wb-layer-ink"
            style={{ position: 'absolute', top: 0, left: 0, display: 'block', touchAction: 'none' }}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={endDrawing}
            onPointerCancel={endDrawing}
            onPointerLeave={endDrawing}
          />

          {/* Floating Text / Equation Input */}
          {floatingTextInput && (
            <div
              className="wb-floating-text-box"
              style={{
                position: 'absolute',
                left: floatingTextInput.xPx,
                top: floatingTextInput.yPx,
                zIndex: 20,
              }}
            >
              <input
                autoFocus
                type="text"
                className="wb-text-equation-input"
                placeholder="Type equation or text (Enter to place, Esc to cancel)..."
                value={floatingTextInput.text}
                onChange={(e) =>
                  setFloatingTextInput((prev) => ({ ...prev, text: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    commitFloatingText();
                  } else if (e.key === 'Escape') {
                    e.preventDefault();
                    cancelFloatingText();
                  }
                }}
                onBlur={commitFloatingText}
              />
            </div>
          )}
        </div>

        {/* Empty Board Watermark (only when no PDF is loaded) */}
        {!pdfDoc && isEmptyWorkspace && (
          <div className="wb-watermark" aria-hidden="true">
            <div className="wb-watermark-icon">✍️</div>
            <div className="wb-watermark-text">Digital Notebook & Canvas</div>
            <div className="wb-watermark-sub">
              Write equations with Pen (P), highlight with (H), or type math with (T)
            </div>
          </div>
        )}

        {/* PDF Loading Indicator */}
        {isLoadingPdf && (
          <div className="wb-watermark">
            <div className="wb-watermark-icon">⏳</div>
            <div className="wb-watermark-text">Rendering PDF Worksheet...</div>
          </div>
        )}

        {/* PDF Error Notice */}
        {pdfError && (
          <div className="wb-watermark" style={{ color: '#DC2626' }}>
            <div className="wb-watermark-icon">⚠️</div>
            <div className="wb-watermark-text">Failed to load PDF</div>
            <div className="wb-watermark-sub">{pdfError}</div>
          </div>
        )}
      </div>

      {/* Snapshot Verification Toast (Dev / QA) */}
      {snapshotPreview && (
        <div className="wb-snapshot-toast" role="alert" aria-live="polite">
          <div className="wb-snapshot-toast-header">
            <span className="wb-snapshot-badge">
              {snapshotPreview.hasPdf ? `PDF Page ${snapshotPreview.pageNum}` : 'Composite Canvas'} Snapshot
            </span>
            <button
              type="button"
              className="wb-snapshot-close"
              onClick={() => setSnapshotPreview(null)}
              aria-label="Close preview"
            >
              ✕
            </button>
          </div>
          <div className="wb-snapshot-toast-body">
            <img
              src={snapshotPreview.dataUrl}
              alt="Snapshot Verification Preview"
              className="wb-snapshot-thumb"
            />
            <div className="wb-snapshot-meta">
              <div>Dimensions: {snapshotPreview.width} × {snapshotPreview.height}</div>
              <div>Payload size: ~{snapshotPreview.bytes ? Math.round(snapshotPreview.bytes / 1024) : 0} KB</div>
              <div>Strokes & Annotations: {snapshotPreview.strokeCount}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export default Whiteboard;
