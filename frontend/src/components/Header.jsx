import React from 'react';
import LanguageSelector from './LanguageSelector';

const STATUS_CONFIG = {
  ready: { label: 'Ready', className: 'status-ready', dotClass: 'dot-ready' },
  listening: { label: 'Listening...', className: 'status-listening', dotClass: 'dot-listening' },
  transcribing: { label: 'Transcribing...', className: 'status-transcribing', dotClass: 'dot-transcribing' },
  thinking: { label: 'Thinking...', className: 'status-thinking', dotClass: 'dot-thinking' },
  checking: { label: 'Checking step...', className: 'status-checking', dotClass: 'dot-checking' },
  speaking: { label: 'Speaking...', className: 'status-speaking', dotClass: 'dot-speaking' },
};

export default function Header({
  subject = 'Maths',
  onSubjectChange,
  language = 'indic-auto',
  onLanguageChange,
  tutorStatus = 'ready',
  backendConnected = false,
  onNewSession,
  inputSource = 'whiteboard',
  onInputSourceChange,
}) {
  const currentStatus = STATUS_CONFIG[tutorStatus] || STATUS_CONFIG.ready;

  return (
    <header className="app-header">
      <div className="header-left">
        <div className="logo-badge">
          <span className="logo-icon">🎓</span>
          <div className="logo-text">
            <h1 className="logo-title">Agentic Learning Tutor</h1>
            <span className="logo-tag">Multilingual AI &bull; SymPy Verifier</span>
          </div>
        </div>

        {/* Subject Selector */}
        <div className="subject-selector" role="radiogroup" aria-label="Tutoring Subject">
          <button
            type="button"
            className={`subject-btn ${subject === 'Maths' ? 'subject-btn-active' : ''}`}
            onClick={() => onSubjectChange?.('Maths')}
            role="radio"
            aria-checked={subject === 'Maths'}
          >
            📐 Maths
          </button>
          <button
            type="button"
            className={`subject-btn ${subject === 'Science' ? 'subject-btn-active' : ''}`}
            onClick={() => onSubjectChange?.('Science')}
            role="radio"
            aria-checked={subject === 'Science'}
          >
            🔬 Science
          </button>
        </div>

        {/* Workspace Mode: Whiteboard vs PDF Worksheet */}
        {onInputSourceChange && (
          <div className="workspace-source-switch" role="radiogroup" aria-label="Workspace View Mode">
            <button
              type="button"
              className={`source-switch-btn ${inputSource === 'whiteboard' ? 'source-active' : ''}`}
              onClick={() => onInputSourceChange?.('whiteboard')}
              title="Interactive drawing whiteboard"
              aria-checked={inputSource === 'whiteboard'}
            >
              <span>✏️ Board</span>
            </button>
            <button
              type="button"
              className={`source-switch-btn ${inputSource === 'pdf' ? 'source-active' : ''}`}
              onClick={() => onInputSourceChange?.('pdf')}
              title="Upload and inspect PDF worksheets"
              aria-checked={inputSource === 'pdf'}
            >
              <span>📄 PDF</span>
            </button>
          </div>
        )}
      </div>

      <div className="header-right">
        {/* Language Selector */}
        <LanguageSelector
          selectedLanguage={language}
          onLanguageChange={onLanguageChange}
        />

        {/* Compact Tutor Status Pill */}
        <div className={`status-pill ${currentStatus.className}`} title={`Tutor status: ${currentStatus.label}`}>
          <span className={`status-dot ${currentStatus.dotClass}`} />
          <span className="status-label">{currentStatus.label}</span>
        </div>

        {/* Backend Health Dot */}
        <div
          className={`health-dot ${backendConnected ? 'health-dot-online' : 'health-dot-offline'}`}
          title={backendConnected ? 'Backend API: Connected' : 'Backend API: Offline'}
          aria-label={backendConnected ? 'Backend Online' : 'Backend Offline'}
        />

        {/* New Session Button */}
        <button
          type="button"
          className="btn-new-session"
          onClick={() => onNewSession?.()}
          title="Reset Whiteboard and start a new tutoring session"
          aria-label="Start new session"
        >
          <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
            <path d="M21 3v5h-5" />
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
            <path d="M8 16H3v5" />
          </svg>
          <span className="btn-label-desktop">New Session</span>
        </button>
      </div>
    </header>
  );
}
