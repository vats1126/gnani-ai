import React, { useRef, useEffect, useState, useCallback, useImperativeHandle, forwardRef } from 'react';
import {
  normalizePoint,
  normalizeLineWidth,
  redrawCanvas,
  exportCanvasSnapshot,
  PAPER_BG,
  DEMO_PRESETS
} from '../utils/canvas';
import WhiteboardToolbar from './WhiteboardToolbar';

const Whiteboard = forwardRef(function Whiteboard(
  { onSnapshotGenerated, onDemoPresetLoaded, onSwitchToPdf, className = '' },
  ref
) {

  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  // Drawing state
  const [strokes, setStrokes] = useState([]);
  const [redoStack, setRedoStack] = useState([]);
  const [activeTool, setActiveTool] = useState('pen');
  const [activeColor, setActiveColor] = useState('#1E293B');
  const [strokeWidth, setStrokeWidth] = useState(0.006); // Normalized ~4px on 600px width

  // Current stroke being actively drawn
  const isDrawingRef = useRef(false);
  const currentStrokeRef = useRef(null);

  // Snapshot test verification state
  const [snapshotPreview, setSnapshotPreview] = useState(null);

  /**
   * Redraw whenever strokes state changes.
   */
  useEffect(() => {
    if (canvasRef.current) {
      redrawCanvas(canvasRef.current, strokes);
    }
  }, [strokes]);

  /**
   * Handle responsive container resizing via ResizeObserver.
   * Redraws stored normalized strokes so scaling or rotation never distorts or clears work.
   */
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let animationFrameId = null;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0 && canvasRef.current) {
          if (animationFrameId) cancelAnimationFrame(animationFrameId);
          animationFrameId = requestAnimationFrame(() => {
            redrawCanvas(canvasRef.current, strokes, {
              customWidth: width,
              customHeight: height,
            });
          });
        }
      }
    });

    observer.observe(container);

    return () => {
      observer.disconnect();
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    };
  }, [strokes]);

  /**
   * Keyboard shortcuts: Cmd+Z (undo), Cmd+Shift+Z or Ctrl+Y (redo)
   */
  useEffect(() => {
    const handleKeyDown = (e) => {
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
  }, [strokes, redoStack]);

  // Pointer event coordinates mapped to canvas-relative coordinates
  const getCanvasCoords = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      px: e.clientX - rect.left,
      py: e.clientY - rect.top,
      width: rect.width,
      height: rect.height,
    };
  };

  const handlePointerDown = (e) => {
    // Only accept primary button (left click / single finger / pen contact)
    if (e.button !== 0 && e.pointerType === 'mouse') return;

    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // Non-critical fallback if pointer capture fails
    }

    const { px, py, width, height } = getCanvasCoords(e);
    const normPt = normalizePoint(px, py, width, height);

    isDrawingRef.current = true;
    currentStrokeRef.current = {
      tool: activeTool,
      color: activeColor,
      lineWidth: strokeWidth,
      points: [normPt],
    };

    // Draw immediate feedback dot
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;
      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = activeTool === 'eraser' ? PAPER_BG : activeColor;
      const dotRadius = Math.max(2, strokeWidth * Math.min(width, height) / 2);
      ctx.beginPath();
      ctx.arc(px, py, dotRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  };

  const handlePointerMove = (e) => {
    if (!isDrawingRef.current || !currentStrokeRef.current) return;

    const { px, py, width, height } = getCanvasCoords(e);
    const normPt = normalizePoint(px, py, width, height);

    const pts = currentStrokeRef.current.points;
    const lastPt = pts[pts.length - 1];

    // Minimal distance threshold to avoid redundant dense points
    const distSq = (normPt.x - lastPt.x) ** 2 + (normPt.y - lastPt.y) ** 2;
    if (distSq > 0.000002) {
      pts.push(normPt);

      // Incremental render of current segment
      const canvas = canvasRef.current;
      if (canvas && pts.length >= 2) {
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        ctx.save();
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.lineWidth = Math.max(1.5, strokeWidth * Math.min(width, height));
        ctx.strokeStyle = activeTool === 'eraser' ? PAPER_BG : activeColor;

        const p0 = pts[pts.length - 2];
        const p1 = pts[pts.length - 1];
        ctx.beginPath();
        ctx.moveTo(p0.x * width, p0.y * height);
        ctx.lineTo(p1.x * width, p1.y * height);
        ctx.stroke();
        ctx.restore();
      }
    }
  };

  const endDrawing = (e) => {
    if (!isDrawingRef.current) return;
    isDrawingRef.current = false;

    if (e && e.currentTarget && e.currentTarget.hasPointerCapture && e.currentTarget.hasPointerCapture(e.pointerId)) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // Safe ignore
      }
    }

    if (currentStrokeRef.current && currentStrokeRef.current.points.length > 0) {
      const newStrokes = [...strokes, currentStrokeRef.current];
      setStrokes(newStrokes);
      // New action invalidates redo stack
      setRedoStack([]);
      currentStrokeRef.current = null;
    }
  };

  const handleUndo = useCallback(() => {
    if (strokes.length === 0) return;
    const lastStroke = strokes[strokes.length - 1];
    setStrokes((prev) => prev.slice(0, -1));
    setRedoStack((prev) => [...prev, lastStroke]);
  }, [strokes]);

  const handleRedo = useCallback(() => {
    if (redoStack.length === 0) return;
    const nextStroke = redoStack[redoStack.length - 1];
    setRedoStack((prev) => prev.slice(0, -1));
    setStrokes((prev) => [...prev, nextStroke]);
  }, [redoStack]);

  const handleClear = useCallback(() => {
    if (strokes.length === 0) return;
    setStrokes([]);
    setRedoStack([]);
  }, [strokes]);

  // Expose exportCanvasSnapshot via ref or component action
  const captureSnapshot = useCallback(() => {
    if (!canvasRef.current) return null;
    const snapshot = exportCanvasSnapshot(canvasRef.current, strokes, 1400, 0.85);
    if (onSnapshotGenerated) {
      onSnapshotGenerated(snapshot);
    }
    return snapshot;
  }, [strokes, onSnapshotGenerated]);

  useImperativeHandle(ref, () => ({
    captureSnapshot,
    clear: handleClear,
    undo: handleUndo,
    redo: handleRedo,
    loadStrokes: (newStrokes) => {
      setStrokes(newStrokes);
      setRedoStack([]);
      setTimeout(captureSnapshot, 50);
    },
    getStrokeCount: () => strokes.length,
    isEmpty: () => strokes.length === 0,
  }));

  const handleTestSnapshot = () => {
    const result = captureSnapshot();
    if (result) {
      setSnapshotPreview(result);
    }
  };

  const handleSelectDemoPreset = useCallback((presetKey) => {
    const preset = DEMO_PRESETS[presetKey];
    if (!preset) return;
    const newStrokes = preset.getStrokes();
    setStrokes(newStrokes);
    setRedoStack([]);

    setTimeout(() => {
      captureSnapshot();
    }, 50);

    if (onDemoPresetLoaded) {
      onDemoPresetLoaded(presetKey, preset);
    }
  }, [captureSnapshot, onDemoPresetLoaded]);

  return (
    <div className={`wb-container ${className}`}>
      {/* Top Whiteboard Toolbar */}
      <WhiteboardToolbar
        activeTool={activeTool}
        setActiveTool={setActiveTool}
        activeColor={activeColor}
        setActiveColor={setActiveColor}
        strokeWidth={strokeWidth}
        setStrokeWidth={setStrokeWidth}
        canUndo={strokes.length > 0}
        canRedo={redoStack.length > 0}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onClear={handleClear}
        onTestSnapshot={handleTestSnapshot}
        onSelectDemoPreset={handleSelectDemoPreset}
        onSwitchToPdf={onSwitchToPdf}
        strokeCount={strokes.length}
      />


      {/* Drawing Canvas Area */}
      <div className="wb-canvas-wrapper" ref={containerRef}>
        <canvas
          ref={canvasRef}
          className="wb-canvas"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={endDrawing}
          onPointerCancel={endDrawing}
          style={{
            touchAction: 'none',
            userSelect: 'none',
            WebkitUserSelect: 'none',
          }}
          aria-label="Digital Whiteboard Workspace"
        />

        {/* Subtle Watermark when canvas is empty */}
        {strokes.length === 0 && !isDrawingRef.current && (
          <div className="wb-watermark" aria-hidden="true">
            <span className="wb-watermark-icon">✍️</span>
            <p className="wb-watermark-text">Write your equation or problem here</p>
            <p className="wb-watermark-sub">e.g., 2x + 5 = 15 &bull; Solve for x</p>
          </div>
        )}

        {/* Dev Snapshot Verification Modal/Badge */}
        {snapshotPreview && (
          <div className="wb-snapshot-toast" role="status">
            <div className="wb-snapshot-toast-header">
              <span className="wb-snapshot-badge">📸 Snapshot Verified</span>
              <button
                type="button"
                className="wb-snapshot-close"
                onClick={() => setSnapshotPreview(null)}
                aria-label="Dismiss snapshot preview"
              >
                &times;
              </button>
            </div>
            <div className="wb-snapshot-toast-body">
              <img
                src={snapshotPreview.dataUrl}
                alt="Captured Whiteboard Snapshot"
                className="wb-snapshot-thumb"
              />
              <div className="wb-snapshot-meta">
                <div><strong>Resolution:</strong> {snapshotPreview.width} &times; {snapshotPreview.height}px</div>
                <div><strong>Payload:</strong> {(snapshotPreview.bytes / 1024).toFixed(1)} KB</div>
                <div><strong>Strokes:</strong> {snapshotPreview.strokeCount}</div>
                <div className="wb-snapshot-status">Solid white background &bull; Ready for Gemini Live</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

export default Whiteboard;

