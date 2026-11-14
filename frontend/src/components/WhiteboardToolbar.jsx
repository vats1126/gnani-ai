import React, { useState, useRef, useEffect } from 'react';
import { DEMO_PRESETS, PAPER_STYLES } from '../utils/canvas';

const COLORS = [
  { id: 'dark', hex: '#1E293B', label: 'Dark Slate' },
  { id: 'blue', hex: '#2563EB', label: 'Blue' },
  { id: 'crimson', hex: '#DC2626', label: 'Red' },
  { id: 'green', hex: '#16A34A', label: 'Green' },
  { id: 'purple', hex: '#7C3AED', label: 'Purple' },
  { id: 'yellow', hex: '#FACC15', label: 'Yellow' },
];

const STROKE_WIDTHS = [
  { id: 'fine', px: 2, label: 'Fine', normalized: 0.003 },
  { id: 'medium', px: 4, label: 'Medium', normalized: 0.006 },
  { id: 'thick', px: 8, label: 'Thick', normalized: 0.012 },
];

export default function WhiteboardToolbar({
  activeTool = 'pen',
  setActiveTool,
  activeColor = '#1E293B',
  setActiveColor,
  strokeWidth = 0.006,
  setStrokeWidth,
  canUndo = false,
  canRedo = false,
  onUndo,
  onRedo,
  onClear,
  onTestSnapshot,
  onSelectDemoPreset,
  strokeCount = 0,
  // Paper styles
  paperStyle = PAPER_STYLES.MATH_GRID,
  setPaperStyle,
  // PDF controls
  hasPdf = false,
  currentPage = 1,
  numPages = 1,
  onPrevPage,
  onNextPage,
  onZoomIn,
  onZoomOut,
  onUploadPdf,
  onLoadSamplePdf,
  onClosePdf,
  pdfFileName = '',
}) {
  const [showDemoMenu, setShowDemoMenu] = useState(false);
  const [showPaperMenu, setShowPaperMenu] = useState(false);
  const demoMenuRef = useRef(null);
  const paperMenuRef = useRef(null);
  const fileInputRef = useRef(null);

  // Close demo menu on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (demoMenuRef.current && !demoMenuRef.current.contains(e.target)) {
        setShowDemoMenu(false);
      }
      if (paperMenuRef.current && !paperMenuRef.current.contains(e.target)) {
        setShowPaperMenu(false);
      }
    }
    if (showDemoMenu || showPaperMenu) {
      document.addEventListener('pointerdown', handleClickOutside);
    }
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, [showDemoMenu, showPaperMenu]);

  const handleSelectPreset = (key) => {
    setShowDemoMenu(false);
    if (onSelectDemoPreset) {
      onSelectDemoPreset(key);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file && onUploadPdf) {
      onUploadPdf(file);
    }
    e.target.value = '';
  };

  return (
    <div className="wb-toolbar" role="toolbar" aria-label="Whiteboard and Document Controls">
      {/* Primary Tools: Pen, Highlighter, Text, Eraser */}
      <div className="wb-tool-group">
        <button
          type="button"
          className={`wb-btn ${activeTool === 'pen' ? 'wb-btn-active' : ''}`}
          onClick={() => setActiveTool?.('pen')}
          title="Pen (P)"
          aria-label="Pen tool"
          aria-pressed={activeTool === 'pen'}
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
          </svg>
          <span className="wb-btn-label">Pen</span>
        </button>

        <button
          type="button"
          className={`wb-btn ${activeTool === 'highlighter' ? 'wb-btn-active' : ''}`}
          onClick={() => {
            setActiveTool?.('highlighter');
            if (activeColor === '#1E293B') {
              setActiveColor?.('#FACC15');
            }
          }}
          title="Highlighter (H)"
          aria-label="Highlighter tool"
          aria-pressed={activeTool === 'highlighter'}
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m9 11-6 6v3h3l6-6" />
            <path d="m22 7-4.5-4.5a2.121 2.121 0 0 0-3 0l-9.5 9.5 7.5 7.5 9.5-9.5a2.121 2.121 0 0 0 0-3Z" />
          </svg>
          <span className="wb-btn-label">Highlighter</span>
        </button>

        <button
          type="button"
          className={`wb-btn ${activeTool === 'text' ? 'wb-btn-active' : ''}`}
          onClick={() => setActiveTool?.('text')}
          title="Text / Equation Tool (T)"
          aria-label="Text or Equation tool"
          aria-pressed={activeTool === 'text'}
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4 7 4 4 20 4 20 7" />
            <line x1="9" y1="20" x2="15" y2="20" />
            <line x1="12" y1="4" x2="12" y2="20" />
          </svg>
          <span className="wb-btn-label">Text</span>
        </button>

        <button
          type="button"
          className={`wb-btn ${activeTool === 'eraser' ? 'wb-btn-active' : ''}`}
          onClick={() => setActiveTool?.('eraser')}
          title="Eraser (E) - Erases ink without damaging grid or PDF"
          aria-label="Eraser tool"
          aria-pressed={activeTool === 'eraser'}
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21" />
            <path d="M22 21H7" />
            <path d="m5 11 9 9" />
          </svg>
          <span className="wb-btn-label">Eraser</span>
        </button>
      </div>

      {/* Colors (active for Pen, Highlighter, Text) */}
      <div className="wb-tool-group color-group">
        {COLORS.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`wb-color-dot ${activeColor === c.hex && activeTool !== 'eraser' ? 'wb-color-selected' : ''}`}
            style={{ backgroundColor: c.hex }}
            onClick={() => {
              setActiveColor?.(c.hex);
              if (activeTool === 'eraser') setActiveTool?.('pen');
            }}
            title={c.label}
            aria-label={`Color ${c.label}`}
          />
        ))}
      </div>

      {/* Stroke Widths */}
      <div className="wb-tool-group width-group">
        {STROKE_WIDTHS.map((w) => (
          <button
            key={w.id}
            type="button"
            className={`wb-btn-icon ${strokeWidth === w.normalized ? 'wb-btn-active' : ''}`}
            onClick={() => setStrokeWidth?.(w.normalized)}
            title={`${w.label} Stroke (${w.px}px)`}
            aria-label={`${w.label} Stroke`}
          >
            <span
              className="wb-stroke-preview"
              style={{
                width: `${Math.max(4, w.px * 2)}px`,
                height: `${Math.max(4, w.px * 2)}px`,
                backgroundColor: activeTool !== 'eraser' ? activeColor : '#64748B',
              }}
            />
          </button>
        ))}
      </div>

      {/* Paper Style Selector (only when no PDF is loaded) */}
      {!hasPdf && setPaperStyle && (
        <div className="wb-tool-group wb-paper-group" ref={paperMenuRef}>
          <button
            type="button"
            className={`wb-btn ${showPaperMenu ? 'wb-btn-active' : ''}`}
            onClick={() => setShowPaperMenu((prev) => !prev)}
            title="Choose paper style (Math Grid, Ruled, Plain)"
            aria-haspopup="true"
            aria-expanded={showPaperMenu}
          >
            <span className="wb-icon">
              {paperStyle === PAPER_STYLES.MATH_GRID ? '📐' : paperStyle === PAPER_STYLES.RULED ? '📝' : '📄'}
            </span>
            <span className="wb-btn-label">
              {paperStyle === PAPER_STYLES.MATH_GRID ? 'Grid' : paperStyle === PAPER_STYLES.RULED ? 'Ruled' : 'Plain'}
            </span>
            <span className="wb-caret">▾</span>
          </button>

          {showPaperMenu && (
            <div className="wb-paper-dropdown" role="menu">
              <button
                type="button"
                className={`paper-dropdown-item ${paperStyle === PAPER_STYLES.MATH_GRID ? 'item-active' : ''}`}
                onClick={() => { setPaperStyle(PAPER_STYLES.MATH_GRID); setShowPaperMenu(false); }}
              >
                <span>📐</span> Math Grid (24px)
              </button>
              <button
                type="button"
                className={`paper-dropdown-item ${paperStyle === PAPER_STYLES.RULED ? 'item-active' : ''}`}
                onClick={() => { setPaperStyle(PAPER_STYLES.RULED); setShowPaperMenu(false); }}
              >
                <span>📝</span> Ruled Notebook
              </button>
              <button
                type="button"
                className={`paper-dropdown-item ${paperStyle === PAPER_STYLES.PLAIN ? 'item-active' : ''}`}
                onClick={() => { setPaperStyle(PAPER_STYLES.PLAIN); setShowPaperMenu(false); }}
              >
                <span>📄</span> Plain Paper
              </button>
            </div>
          )}
        </div>
      )}

      {/* PDF Controls */}
      <div className="wb-tool-group wb-pdf-group">
        {!hasPdf ? (
          <>
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,application/pdf"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <button
              type="button"
              className="wb-btn wb-btn-pdf"
              onClick={() => fileInputRef.current?.click()}
              title="Upload textbook or worksheet PDF (max 15MB)"
            >
              <span className="wb-icon">📂</span>
              <span className="wb-btn-label">Upload PDF</span>
            </button>
            {onLoadSamplePdf && (
              <button
                type="button"
                className="wb-btn wb-btn-pdf-sample"
                onClick={() => onLoadSamplePdf?.()}
                title="Load sample algebra worksheet PDF"
              >
                <span className="wb-icon">📄</span>
                <span className="wb-btn-label">Sample</span>
              </button>
            )}
          </>
        ) : (
          <div className="wb-pdf-nav-bar">
            <button
              type="button"
              className="wb-btn-icon"
              onClick={() => onPrevPage?.()}
              disabled={currentPage <= 1}
              title="Previous Page"
            >
              ◀
            </button>
            <span className="wb-page-indicator">
              Page {currentPage} / {numPages}
            </span>
            <button
              type="button"
              className="wb-btn-icon"
              onClick={() => onNextPage?.()}
              disabled={currentPage >= numPages}
              title="Next Page"
            >
              ▶
            </button>
            {onZoomOut && (
              <button type="button" className="wb-btn-icon" onClick={() => onZoomOut?.()} title="Zoom Out">
                −
              </button>
            )}
            {onZoomIn && (
              <button type="button" className="wb-btn-icon" onClick={() => onZoomIn?.()} title="Zoom In">
                +
              </button>
            )}
            <button
              type="button"
              className="wb-btn wb-btn-danger-subtle"
              onClick={() => onClosePdf?.()}
              title="Close PDF and return to whiteboard"
            >
              ✕ Close PDF
            </button>
          </div>
        )}
      </div>

      {/* Undo / Redo */}
      <div className="wb-tool-group">
        <button
          type="button"
          className="wb-btn-icon"
          onClick={() => onUndo?.()}
          disabled={!canUndo}
          title="Undo (Cmd+Z)"
          aria-label="Undo last stroke"
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 7v6h6" />
            <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
          </svg>
        </button>

        <button
          type="button"
          className="wb-btn-icon"
          onClick={() => onRedo?.()}
          disabled={!canRedo}
          title="Redo (Cmd+Shift+Z)"
          aria-label="Redo last stroke"
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 7v6h-6" />
            <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7" />
          </svg>
        </button>
      </div>

      {/* Live Demo Examples Menu (Section 15 Hardening) */}
      <div className="wb-tool-group wb-demo-group" ref={demoMenuRef}>
        <button
          type="button"
          className={`wb-btn wb-btn-demo ${showDemoMenu ? 'wb-btn-active' : ''}`}
          onClick={() => setShowDemoMenu((prev) => !prev)}
          title="Load 3-minute pitch demo examples (Section 15)"
          aria-haspopup="true"
          aria-expanded={showDemoMenu}
        >
          <span className="wb-icon">🎯</span>
          <span className="wb-btn-label">Presets</span>
          <span className="wb-caret">▾</span>
        </button>

        {showDemoMenu && (
          <div className="wb-demo-dropdown" role="menu">
            <div className="demo-dropdown-header">Section 15 Live Pitch Presets</div>
            {Object.entries(DEMO_PRESETS).map(([key, preset]) => (
              <button
                key={key}
                type="button"
                className="demo-dropdown-item"
                role="menuitem"
                onClick={() => handleSelectPreset(key)}
              >
                <div className="demo-item-title">{preset.label}</div>
                <div className="demo-item-sub">{preset.suggestedText}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Clear & Dev Snapshot Verification */}
      <div className="wb-tool-group wb-actions-right">
        <button
          type="button"
          className="wb-btn wb-btn-danger"
          onClick={() => onClear?.()}
          disabled={strokeCount === 0}
          title="Clear Ink Annotations"
          aria-label="Clear ink annotations"
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6h18" />
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
          </svg>
          <span className="wb-btn-label">Clear</span>
        </button>

        <button
          type="button"
          className="wb-btn wb-btn-secondary"
          onClick={() => onTestSnapshot?.()}
          title="Generate test composite snapshot to verify AI vision payload"
          aria-label="Test snapshot export"
        >
          <svg className="wb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
            <circle cx="12" cy="13" r="3" />
          </svg>
          <span className="wb-btn-label">Snapshot</span>
        </button>
      </div>
    </div>
  );
}
