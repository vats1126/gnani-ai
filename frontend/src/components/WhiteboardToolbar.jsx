import React, { useState, useRef, useEffect } from 'react';
import { DEMO_PRESETS } from '../utils/canvas';

const COLORS = [
  { id: 'dark', hex: '#1E293B', label: 'Dark Slate' },
  { id: 'blue', hex: '#2563EB', label: 'Blue' },
  { id: 'crimson', hex: '#DC2626', label: 'Red' },
  { id: 'green', hex: '#16A34A', label: 'Green' },
  { id: 'purple', hex: '#7C3AED', label: 'Purple' },
];

const STROKE_WIDTHS = [
  { id: 'fine', px: 2, label: 'Fine', normalized: 0.003 },
  { id: 'medium', px: 4, label: 'Medium', normalized: 0.006 },
  { id: 'thick', px: 8, label: 'Thick', normalized: 0.012 },
];

export default function WhiteboardToolbar({
  activeTool,
  setActiveTool,
  activeColor,
  setActiveColor,
  strokeWidth,
  setStrokeWidth,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onClear,
  onTestSnapshot,
  onSelectDemoPreset,
  onSwitchToPdf,
  strokeCount = 0,
}) {
  const [showDemoMenu, setShowDemoMenu] = useState(false);
  const demoMenuRef = useRef(null);

  // Close demo menu on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (demoMenuRef.current && !demoMenuRef.current.contains(e.target)) {
        setShowDemoMenu(false);
      }
    }
    if (showDemoMenu) {
      document.addEventListener('pointerdown', handleClickOutside);
    }
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, [showDemoMenu]);

  const handleSelectPreset = (key) => {
    setShowDemoMenu(false);
    if (onSelectDemoPreset) {
      onSelectDemoPreset(key);
    }
  };

  return (
    <div className="wb-toolbar" role="toolbar" aria-label="Whiteboard Drawing Controls">
      {/* Primary Tools: Pen & Eraser */}
      <div className="wb-tool-group">
        <button
          type="button"
          className={`wb-btn ${activeTool === 'pen' ? 'wb-btn-active' : ''}`}
          onClick={() => setActiveTool('pen')}
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
          className={`wb-btn ${activeTool === 'eraser' ? 'wb-btn-active' : ''}`}
          onClick={() => setActiveTool('eraser')}
          title="Eraser (E)"
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

      {/* Colors (only active when Pen is selected) */}
      <div className="wb-tool-group color-group">
        {COLORS.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`wb-color-dot ${activeColor === c.hex && activeTool === 'pen' ? 'wb-color-selected' : ''}`}
            style={{ backgroundColor: c.hex }}
            onClick={() => {
              setActiveColor(c.hex);
              setActiveTool('pen');
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
            onClick={() => setStrokeWidth(w.normalized)}
            title={`${w.label} Stroke (${w.px}px)`}
            aria-label={`${w.label} Stroke`}
          >
            <span
              className="wb-stroke-preview"
              style={{
                width: `${Math.max(4, w.px * 2)}px`,
                height: `${Math.max(4, w.px * 2)}px`,
                backgroundColor: activeTool === 'pen' ? activeColor : '#64748B',
              }}
            />
          </button>
        ))}
      </div>

      {/* Undo / Redo */}
      <div className="wb-tool-group">
        <button
          type="button"
          className="wb-btn-icon"
          onClick={onUndo}
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
          onClick={onRedo}
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
          <span className="wb-btn-label">Demo Presets</span>
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

      {/* PDF Worksheet Switch Button */}
      {onSwitchToPdf && (
        <div className="wb-tool-group">
          <button
            type="button"
            className="wb-btn wb-btn-pdf"
            onClick={onSwitchToPdf}
            title="Switch to PDF Worksheet Viewer (Section 6 & 7C)"
            aria-label="Switch to PDF Worksheet"
          >
            <span className="wb-icon">📄</span>
            <span className="wb-btn-label">PDF Worksheet</span>
          </button>
        </div>
      )}

      {/* Clear & Dev Snapshot Verification */}
      <div className="wb-tool-group wb-actions-right">
        <button
          type="button"
          className="wb-btn wb-btn-danger"
          onClick={onClear}
          disabled={strokeCount === 0}
          title="Clear Whiteboard"
          aria-label="Clear whiteboard"
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
          onClick={onTestSnapshot}
          title="Generate test snapshot to verify AI vision payload"
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
