import React, { useRef, useEffect } from 'react';
import FeedbackBadge from './FeedbackBadge';

export default function TutorPanel({
  messages = [],
  onQuickAction,
  subject = 'Maths',
  language = 'indic-auto',
  latestSnapshot = null,
  isTutorThinking = false,
  tutorStatus = 'ready',
  autoSpeak = true,
  onToggleAutoSpeak,
  onPlayAudio,
  onStopAudio,
  currentlyPlayingMsgId = null,
  audioLoadingMsgId = null,
}) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTutorThinking]);

  return (
    <div className="tutor-panel">
      {/* Panel Header */}
      <div className="tutor-panel-header">
        <div className="tutor-header-title">
          <span className="tutor-avatar">🤖</span>
          <div>
            <h2 className="tutor-heading">AI Tutor</h2>
            <span className="tutor-subheading">Gemini Live &bull; SymPy CAS &bull; Gnani Voice</span>
          </div>
        </div>

        {/* Header Right Actions */}
        <div className="tutor-header-actions">
          {/* Auto-Speak toggle switch */}
          {onToggleAutoSpeak && (
            <button
              type="button"
              className={`tutor-voice-toggle-btn ${autoSpeak ? 'voice-active' : ''}`}
              onClick={onToggleAutoSpeak}
              title={autoSpeak ? 'Auto-Voice enabled: Tutor answers are read aloud' : 'Auto-Voice muted: Click Listen to hear speech'}
              aria-label={autoSpeak ? 'Disable Auto-Voice' : 'Enable Auto-Voice'}
            >
              <span>{autoSpeak ? '🔊 Auto-Voice: ON' : '🔇 Auto-Voice: OFF'}</span>
            </button>
          )}

          {/* Live snapshot mini-indicator */}
          {latestSnapshot && (
            <div className="tutor-snapshot-pill" title="Tutor has visual awareness of the latest whiteboard snapshot">
              <span className="snapshot-pulse" />
              <span>Board Synced</span>
            </div>
          )}
        </div>
      </div>

      {/* Quick Action Chips (44px+ accessible tap targets) */}
      <div className="quick-actions-bar" role="group" aria-label="Suggested quick questions">
        <button
          type="button"
          className="quick-chip"
          onClick={() => onQuickAction('hint', 'Can you give me a small hint for this step?')}
        >
          💡 Hint
        </button>
        <button
          type="button"
          className="quick-chip"
          onClick={() => onQuickAction('check_work', 'Please check my work on the board and tell me if this step is correct.')}
        >
          🔍 Check work
        </button>
        <button
          type="button"
          className="quick-chip"
          onClick={() => onQuickAction('explain_simply', 'Can you explain this concept in simpler words?')}
        >
          📖 Explain simply
        </button>
        <button
          type="button"
          className="quick-chip"
          onClick={() => onQuickAction('practice', 'Can you give me a practice problem to solve on the board?')}
        >
          🎯 Practice
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="tutor-messages-container">
        {messages.length === 0 ? (
          <div className="tutor-empty-state">
            <div className="empty-bubble-icon">✏️</div>
            <h3 className="empty-title">Ready to learn {subject}</h3>
            <p className="empty-description">
              Write an equation on the board or press the mic button to speak in your language.
            </p>
            <div className="empty-tips">
              <span className="tip-pill">🔍 SymPy CAS step verification</span>
              <span className="tip-pill">🎙️ Press mic to talk</span>
              <span className="tip-pill">💡 Step-by-step Socratic hints</span>
              <span className="tip-pill">🎯 Practice questions on demand</span>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((msg, index) => {
              const isStudent = msg.sender === 'student';
              const isError = msg.isError === true;
              const msgKey = msg.id || index;
              const isPlaying = currentlyPlayingMsgId === msgKey;
              const isLoadingAudio = audioLoadingMsgId === msgKey;

              return (
                <div
                  key={msgKey}
                  className={`message-row ${
                    isStudent ? 'message-student' : isError ? 'message-tutor-error' : 'message-tutor'
                  }`}
                >
                  <div className={`message-bubble ${isError ? 'bubble-error' : ''}`}>
                    <div className="message-header">
                      <span className="message-sender">
                        {isStudent ? 'You (Student)' : isError ? '⚠️ Tutor Notice' : 'AI Tutor'}
                      </span>
                      {msg.timestamp && (
                        <span className="message-time">{msg.timestamp}</span>
                      )}
                    </div>

                    <div className="message-text">{msg.text}</div>

                    {/* Whiteboard Snapshot thumbnail if attached to student turn */}
                    {msg.snapshotThumbnail && (
                      <div className="message-snapshot-preview">
                        <img
                          src={msg.snapshotThumbnail}
                          alt="Whiteboard state at time of question"
                          className="message-snapshot-img"
                        />
                        <span className="message-snapshot-label">
                          {msg.hasPdf ? 'PDF worksheet page attached' : 'Whiteboard snapshot attached'}
                        </span>
                      </div>
                    )}

                    {/* SymPy Verification Badge if provided on tutor turn */}
                    {!isStudent && msg.verdict && msg.verdict !== 'not_applicable' && (
                      <div className="message-feedback-wrapper">
                        <FeedbackBadge
                          status={msg.verdict}
                          detail={
                            msg.verdictDetail ||
                            (msg.verdict === 'correct'
                              ? 'SymPy CAS: Deterministically Verified'
                              : msg.verdict === 'incorrect'
                              ? 'SymPy CAS: Algebraic Mismatch Detected'
                              : 'Step evaluation pending formal CAS verification')
                          }
                        />
                      </div>
                    )}

                    {/* Step-by-step notes from SymPy verifier */}
                    {!isStudent && msg.steps && msg.steps.length > 0 && (
                      <div className="message-verifier-steps">
                        {msg.steps.map((st, i) => (
                          <div key={i} className="verifier-step-item">
                            <span className="verifier-step-bullet">ℹ️</span>
                            <span className="verifier-step-text">{st}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Next suggestion pill */}
                    {!isStudent && msg.next_suggestion && (
                      <div className="next-suggestion-box">
                        <span className="next-suggestion-label">Suggested next step:</span> {msg.next_suggestion}
                      </div>
                    )}

                    {/* Milestone 4: Audio Playback & Replay Controls */}
                    {!isStudent && !isError && onPlayAudio && (
                      <div className="message-audio-controls">
                        {isPlaying ? (
                          <button
                            type="button"
                            className="btn-audio-action btn-audio-stop"
                            onClick={onStopAudio}
                            title="Stop playing voice"
                            aria-label="Stop audio"
                          >
                            <span>⏹ Stop Voice</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn-audio-action btn-audio-play"
                            onClick={() => onPlayAudio(msg, msgKey)}
                            disabled={isLoadingAudio}
                            title="Read answer aloud using Gnani Timbre TTS"
                            aria-label="Read answer aloud"
                          >
                            {isLoadingAudio ? (
                              <span>⏳ Synthesizing...</span>
                            ) : (
                              <span>🔊 {msg.hasSpoken ? 'Replay Voice' : 'Listen'}</span>
                            )}
                          </button>
                        )}
                        {msg.language_code && msg.language_code !== 'indic-auto' && (
                          <span className="audio-locale-tag" title="Language code">
                            {msg.language_code}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Tutor Thinking / Checking / Speaking Bubble */}
            {isTutorThinking && (
              <div className="message-row message-tutor">
                <div className="message-bubble thinking-bubble">
                  <div className="thinking-dots">
                    <span className="thinking-dot" />
                    <span className="thinking-dot" />
                    <span className="thinking-dot" />
                  </div>
                  <span className="thinking-text">
                    {tutorStatus === 'checking'
                      ? 'Verifying equation step with SymPy CAS...'
                      : tutorStatus === 'transcribing'
                      ? 'Transcribing your voice with Gnani Prisma...'
                      : tutorStatus === 'speaking'
                      ? 'Synthesizing voice with Gnani Timbre...'
                      : 'Tutor is thinking with Gemini Live...'}
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}
