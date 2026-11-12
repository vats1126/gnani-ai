import React, { useState, useRef, useEffect, useCallback } from 'react';
import { AudioRecorder } from '../utils/audio';

export default function VoiceButton({
  isRecording = false,
  onRecordingStart,
  onRecordingComplete,
  onError,
  disabled = false,
  maxDurationSeconds = 25,
}) {
  const [elapsed, setElapsed] = useState(0);
  const [micError, setMicError] = useState(null);
  const recorderRef = useRef(null);

  // Clean up media recorder on unmount
  useEffect(() => {
    return () => {
      if (recorderRef.current) {
        recorderRef.current.cleanup();
      }
    };
  }, []);

  const handleToggle = useCallback(async () => {
    setMicError(null);

    // If currently recording, STOP recording
    if (isRecording) {
      if (recorderRef.current) {
        try {
          const result = await recorderRef.current.stop();
          recorderRef.current = null;
          setElapsed(0);
          if (result && result.wavBlob) {
            if (onRecordingComplete) {
              onRecordingComplete(result);
            }
          }
        } catch (err) {
          const msg = err.message || 'Error stopping recording';
          setMicError(msg);
          if (onError) onError(msg);
        }
      }
      return;
    }

    // If not recording, START recording
    try {
      const recorder = new AudioRecorder({
        maxDurationSeconds,
        onProgress: (sec) => {
          setElapsed(sec);
        },
        onAutoStop: async () => {
          try {
            const result = await recorder.stop();
            recorderRef.current = null;
            setElapsed(0);
            if (result && result.wavBlob) {
              if (onRecordingComplete) {
                onRecordingComplete(result);
              }
            }
          } catch (err) {
            const msg = err.message || 'Auto-stop recording failed';
            setMicError(msg);
            if (onError) onError(msg);
          }
        },
      });

      recorderRef.current = recorder;
      await recorder.start();
      setElapsed(0);
      if (onRecordingStart) onRecordingStart();
    } catch (err) {
      recorderRef.current = null;
      setElapsed(0);
      const friendlyMsg = err.message.toLowerCase().includes('denied')
        ? 'Microphone access denied. You can continue typing your question below.'
        : `Microphone error: ${err.message}`;
      setMicError(friendlyMsg);
      if (onError) onError(friendlyMsg);
    }
  }, [isRecording, onRecordingStart, onRecordingComplete, onError, maxDurationSeconds]);

  // Format seconds into mm:ss
  const formatTime = (sec) => {
    const s = Math.floor(sec);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${rem.toString().padStart(2, '0')}`;
  };

  return (
    <div className="voice-btn-container">
      <button
        type="button"
        className={`voice-mic-btn ${isRecording ? 'voice-mic-recording' : ''}`}
        onClick={handleToggle}
        disabled={disabled}
        title={isRecording ? 'Click to stop recording' : 'Press to talk in your language (Gnani Prisma STT)'}
        aria-label={isRecording ? 'Stop voice recording' : 'Start voice recording'}
      >
        {isRecording ? (
          <svg className="voice-mic-icon" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg className="voice-mic-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        )}
        {isRecording && <span className="voice-record-ping" />}
      </button>

      {/* Recording elapsed timer pill */}
      {isRecording && (
        <span className="voice-timer-pill" aria-live="polite">
          <span className="voice-rec-dot" />
          {formatTime(elapsed)} / {formatTime(maxDurationSeconds)}
        </span>
      )}

      {/* Non-blocking permission or recording error message */}
      {micError && (
        <div className="voice-mic-error-toast" role="alert">
          <span>{micError}</span>
          <button type="button" className="toast-close" onClick={() => setMicError(null)}>✕</button>
        </div>
      )}
    </div>
  );
}
