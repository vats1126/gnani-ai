import React, { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import Whiteboard from './components/Whiteboard';
import TutorPanel from './components/TutorPanel';
import VoiceButton from './components/VoiceButton';
import {
  fetchHealth,
  sendTutorTurn,
  resetTutorSession,
  transcribeAudio,
  speakText,
  verifyMathStep,
  fetchPracticeQuestion,
} from './services/api';
import { playWavBlob, stopCurrentAudio, speakWithBrowserFallback } from './utils/audio';

// Safe UUID generation with fallback
function generateSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'sess_' + Math.random().toString(36).substring(2, 11) + Date.now().toString(36);
}

export default function App() {
  // Session & Metadata state
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('tutor_session_id') || generateSessionId();
  });
  const [subject, setSubject] = useState('Maths');
  const [language, setLanguage] = useState('indic-auto');
  const [tutorStatus, setTutorStatus] = useState('ready');
  const [backendConnected, setBackendConnected] = useState(false);

  // Workspace Mode: 'whiteboard' | 'pdf' (Section 6 & 7C)
  const [inputSource, setInputSource] = useState('whiteboard');

  // Responsive mobile tab state: 'whiteboard' | 'tutor'
  const [mobileTab, setMobileTab] = useState('whiteboard');

  // Component refs
  const whiteboardRef = useRef(null);
  const [latestSnapshot, setLatestSnapshot] = useState(null);

  // Conversation history
  const [messages, setMessages] = useState([]);
  const [typedQuestion, setTypedQuestion] = useState('');
  const [isTutorThinking, setIsTutorThinking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  // Audio Playback & Auto-Speak state (Milestone 4)
  const [autoSpeak, setAutoSpeak] = useState(() => {
    const saved = localStorage.getItem('tutor_auto_speak');
    return saved !== null ? saved === 'true' : true;
  });
  const [currentlyPlayingMsgId, setCurrentlyPlayingMsgId] = useState(null);
  const [audioLoadingMsgId, setAudioLoadingMsgId] = useState(null);
  const [deviceVoiceNotice, setDeviceVoiceNotice] = useState(false);

  // In-flight request lock & debounce guard (Milestone 7)
  const lastActionTimeRef = useRef(0);
  const isExecutingRef = useRef(false);

  // Persist session_id in localStorage
  useEffect(() => {
    localStorage.setItem('tutor_session_id', sessionId);
  }, [sessionId]);

  // Persist autoSpeak preference
  useEffect(() => {
    localStorage.setItem('tutor_auto_speak', autoSpeak.toString());
  }, [autoSpeak]);

  // Periodic backend health check
  const checkHealth = useCallback(async () => {
    const data = await fetchHealth();
    setBackendConnected(data.ok === true);
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Stop any active audio and reset state on new session
  const handleNewSession = useCallback(async () => {
    stopCurrentAudio();
    setCurrentlyPlayingMsgId(null);
    setAudioLoadingMsgId(null);

    const oldSessionId = sessionId;
    const newId = generateSessionId();
    setSessionId(newId);
    setMessages([]);
    setLatestSnapshot(null);
    setTutorStatus('ready');
    setIsTutorThinking(false);

    if (whiteboardRef.current) {
      whiteboardRef.current.clear();
    }

    // Clean up active backend session connection asynchronously
    await resetTutorSession(oldSessionId);
  }, [sessionId]);

  // Stop any audio when unmounting
  useEffect(() => {
    return () => {
      stopCurrentAudio();
    };
  }, []);

  // Helper: Play synthesized audio for a tutor message
  const playTutorAudio = useCallback((blob, msgId) => {
    setCurrentlyPlayingMsgId(msgId);
    setTutorStatus('speaking');

    playWavBlob(
      blob,
      () => {
        setTutorStatus('speaking');
      },
      () => {
        setCurrentlyPlayingMsgId(null);
        setTutorStatus('ready');
      },
      () => {
        setCurrentlyPlayingMsgId(null);
        setTutorStatus('ready');
      }
    );
  }, []);

  // Manual Play / Replay button clicked on a tutor message
  const handlePlayAudio = useCallback(async (msg, msgId) => {
    stopCurrentAudio();

    if (msg.audioBlob) {
      playTutorAudio(msg.audioBlob, msgId);
      return;
    }

    // Synthesize on-demand using Gnani Timbre TTS
    setAudioLoadingMsgId(msgId);
    setTutorStatus('speaking');

    const res = await speakText(msg.text, msg.language_code || language);
    setAudioLoadingMsgId(null);

    if (res.ok && res.blob) {
      setMessages((prev) =>
        prev.map((m) =>
          (m.id || null) === msgId ? { ...m, audioBlob: res.blob, hasSpoken: true } : m
        )
      );
      playTutorAudio(res.blob, msgId);
    } else {
      // Automatic fallback to native browser SpeechSynthesis (Milestone 7)
      setDeviceVoiceNotice(true);
      setTimeout(() => setDeviceVoiceNotice(false), 4000);
      setCurrentlyPlayingMsgId(msgId);
      setTutorStatus('speaking');
      speakWithBrowserFallback(
        msg.text,
        msg.language_code || language,
        () => setTutorStatus('speaking'),
        () => {
          setCurrentlyPlayingMsgId(null);
          setTutorStatus('ready');
        },
        () => {
          setCurrentlyPlayingMsgId(null);
          setTutorStatus('ready');
        }
      );
    }
  }, [language, playTutorAudio]);

  // Stop currently playing voice
  const handleStopAudio = useCallback(() => {
    stopCurrentAudio();
    setCurrentlyPlayingMsgId(null);
    setTutorStatus('ready');
  }, []);

  // Handle switching between digital whiteboard and PDF worksheet
  const handleInputSourceChange = useCallback((newSource) => {
    setInputSource(newSource);
    if (newSource === 'pdf') {
      if (!whiteboardRef.current?.hasPdf?.()) {
        whiteboardRef.current?.loadSamplePdf?.();
      }
    } else {
      if (whiteboardRef.current?.hasPdf?.()) {
        whiteboardRef.current?.closePdf?.();
      }
    }
  }, []);

  // Execute a student turn against /api/tutor/turn
  const executeTurn = useCallback(async (actionType = 'ask', overrideText = null, overrideLang = null) => {
    stopCurrentAudio();
    setCurrentlyPlayingMsgId(null);

    // In-flight request lock & 800ms debounce guard (Milestone 7)
    const now = Date.now();
    if (isExecutingRef.current || (now - lastActionTimeRef.current < 800)) {
      return;
    }
    lastActionTimeRef.current = now;
    isExecutingRef.current = true;

    try {
      const questionText = (overrideText !== null ? overrideText : typedQuestion).trim();

      // 1. Capture visual snapshot from unified whiteboard
      const snapshot = whiteboardRef.current?.exportCompositeSnapshot?.() || whiteboardRef.current?.captureSnapshot?.();

      if (snapshot) {
        setLatestSnapshot(snapshot);
      }

      const hasPdf = Boolean(snapshot?.hasPdf ?? whiteboardRef.current?.hasPdf?.() ?? (inputSource === 'pdf'));
      const turnInputSource = hasPdf ? 'pdf' : 'whiteboard';

      const isBoardEmpty = whiteboardRef.current ? whiteboardRef.current.isEmpty() : true;
      const hasVisualPayload = snapshot !== null;

      // Allow asking if student provided either text or visual workspace content
      if (!questionText && isBoardEmpty && !hasVisualPayload) {
        return;
      }

      const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // 2. Append Student Turn to conversation list
      const studentTurn = {
        id: 'msg_student_' + Date.now(),
        sender: 'student',
        text: questionText || (turnInputSource === 'pdf' ? '(Sent PDF worksheet page for review)' : '(Sent whiteboard drawing for review)'),
        snapshotThumbnail: snapshot?.dataUrl || latestSnapshot?.dataUrl || null,
        hasPdf,
        timestamp,
      };

      setMessages((prev) => [...prev, studentTurn]);
      setTypedQuestion('');
      setIsTutorThinking(true);

      // Update status pill per Section 8: Checking step for check_work, Thinking for others
      if (actionType === 'check_work') {
        setTutorStatus('checking');
      } else {
        setTutorStatus('thinking');
      }

      // Automatically switch to Tutor tab on mobile so student sees response immediately
      if (window.innerWidth < 768) {
        setMobileTab('tutor');
      }

      const activeLanguage = overrideLang || language;

      // Extract recent history for stateless hydration across cold serverless instances
      const recentHistory = messages.slice(-6).map((m) => ({
        role: m.sender === 'tutor' ? 'tutor' : 'student',
        text: m.text || '',
      }));

      // 3. Build payload and invoke /api/tutor/turn
      const payload = {
        session_id: sessionId,
        subject: subject.toLowerCase(),
        learner_level: 'school',
        language_code: activeLanguage,
        message: questionText,
        input_source: turnInputSource,
        whiteboard_image_base64: snapshot?.dataUrl || latestSnapshot?.dataUrl || null,
        action: actionType,
        history: recentHistory,
      };

      const res = await sendTutorTurn(payload);

      setIsTutorThinking(false);

      const replyTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      if (res.ok && res.data) {
        const tutorTurnId = 'msg_tutor_' + Date.now();
        const tutorTurn = {
          id: tutorTurnId,
          sender: 'tutor',
          text: res.data.answer,
          verdict: res.data.verdict,
          steps: res.data.steps || [],
          next_suggestion: res.data.next_suggestion,
          language_code: res.data.language_code || activeLanguage,
          timestamp: replyTime,
          audioBlob: null,
          hasSpoken: false,
        };

        setMessages((prev) => [...prev, tutorTurn]);

        // If Auto-Speak is enabled, synthesize and speak the answer immediately (Section 7A)
        if (autoSpeak && res.data.answer) {
          setTutorStatus('speaking');
          setAudioLoadingMsgId(tutorTurnId);

          const speechRes = await speakText(res.data.answer, res.data.language_code || activeLanguage);
          setAudioLoadingMsgId(null);

          if (speechRes.ok && speechRes.blob) {
            tutorTurn.audioBlob = speechRes.blob;
            tutorTurn.hasSpoken = true;
            setMessages((prev) =>
              prev.map((m) => (m.id === tutorTurnId ? { ...m, audioBlob: speechRes.blob, hasSpoken: true } : m))
            );
            playTutorAudio(speechRes.blob, tutorTurnId);
          } else {
            // Automatic fallback to native browser SpeechSynthesis (Milestone 7)
            setDeviceVoiceNotice(true);
            setTimeout(() => setDeviceVoiceNotice(false), 4000);
            setCurrentlyPlayingMsgId(tutorTurnId);
            setTutorStatus('speaking');
            speakWithBrowserFallback(
              res.data.answer,
              res.data.language_code || activeLanguage,
              () => setTutorStatus('speaking'),
              () => {
                setCurrentlyPlayingMsgId(null);
                setTutorStatus('ready');
              },
              () => {
                setCurrentlyPlayingMsgId(null);
                setTutorStatus('ready');
              }
            );
          }
        } else {
          setTutorStatus('ready');
        }
      } else {
      setTutorStatus('ready');
      const err = res.error || {};

      // Local fallback for practice questions if Gemini key is not configured
      if (err.code === 'GEMINI_NOT_CONFIGURED' && actionType === 'practice') {
        const pqRes = await fetchPracticeQuestion(subject.toLowerCase(), 'easy', activeLanguage);
        if (pqRes.ok && pqRes.data) {
          const pq = pqRes.data;
          const practiceTurn = {
            id: 'msg_tutor_' + Date.now(),
            sender: 'tutor',
            text: `${pq.question}\n\nWrite your first step on the board or click Hint for guidance!`,
            verdict: 'not_applicable',
            steps: [`Equation: ${pq.equation}`, `Variable: ${pq.variable}`],
            next_suggestion: pq.hint,
            language_code: activeLanguage,
            timestamp: replyTime,
            audioBlob: null,
            hasSpoken: false,
          };
          setMessages((prev) => [...prev, practiceTurn]);
          return;
        }
      }

      // Local fallback for check_work if Gemini key is not configured and student typed equations
      if (err.code === 'GEMINI_NOT_CONFIGURED' && actionType === 'check_work') {
        const parts = questionText.split(/[,;\n]|\band\b/i).map((s) => s.trim()).filter((s) => s.includes('='));
        if (parts.length >= 2) {
          const vRes = await verifyMathStep(parts[0], parts[1]);
          if (vRes.ok && vRes.data) {
            const ver = vRes.data;
            const checkedTurn = {
              id: 'msg_tutor_' + Date.now(),
              sender: 'tutor',
              text: ver.reason,
              verdict: ver.status,
              steps: [ver.reason],
              next_suggestion: ver.expected_next_step,
              language_code: activeLanguage,
              timestamp: replyTime,
              audioBlob: null,
              hasSpoken: false,
            };
            setMessages((prev) => [...prev, checkedTurn]);
            return;
          }
        }
      }

      // Structured error response handling matching Section 11
      let alertText = err.message || 'An error occurred while contacting the AI tutor.';
      if (err.code === 'GEMINI_NOT_CONFIGURED') {
        alertText = 'Gemini API Key is not configured. Please add your GEMINI_API_KEY in backend/.env to enable live Gemini tutoring.';
      }

      const errorTurn = {
        id: 'msg_error_' + Date.now(),
        sender: 'tutor',
        isError: true,
        text: alertText,
        errorCode: err.code || 'ERROR',
        timestamp: replyTime,
      };
      setMessages((prev) => [...prev, errorTurn]);
    }
  } finally {
    isExecutingRef.current = false;
  }
}, [sessionId, subject, language, typedQuestion, inputSource, latestSnapshot, autoSpeak, playTutorAudio]);

  // Quick Action chips in TutorPanel
  const handleQuickAction = useCallback((action, defaultPrompt) => {
    const textToUse = typedQuestion.trim() || defaultPrompt;
    executeTurn(action, textToUse);
  }, [typedQuestion, executeTurn]);

  // Handle Demo Presets Loaded from WhiteboardToolbar (Section 15 Hardening)
  const handleDemoPresetLoaded = useCallback((presetKey, preset) => {
    if (preset.subject) {
      setSubject(preset.subject);
    }
    if (preset.suggestedText) {
      setTypedQuestion(preset.suggestedText);
    }
  }, []);

  // Voice Pipeline handlers (Milestone 4: Section 7A)
  const handleVoiceRecordStart = useCallback(() => {
    stopCurrentAudio();
    setIsRecording(true);
    setTutorStatus('listening');
  }, []);

  const handleVoiceRecordComplete = useCallback(async ({ wavBlob, duration }) => {
    setIsRecording(false);
    setTutorStatus('transcribing');

    // 1. Upload WAV to Gnani Prisma STT
    const res = await transcribeAudio(wavBlob, language);

    if (!res.ok) {
      setTutorStatus('ready');
      const err = res.error || {};
      let errorMsg = err.message || 'Voice transcription failed.';
      if (err.code === 'GNANI_NOT_CONFIGURED') {
        errorMsg = 'Gnani Voice is not configured. Please add GNANI_API_KEY in backend/.env to use voice speech-to-text.';
      }

      const errorTurn = {
        id: 'msg_error_' + Date.now(),
        sender: 'tutor',
        isError: true,
        text: errorMsg,
        errorCode: err.code || 'GNANI_ERROR',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorTurn]);
      return;
    }

    const transcript = res.data?.transcript?.trim();
    const detectedLang = res.data?.detected_language_code;

    if (!transcript) {
      setTutorStatus('ready');
      return;
    }

    // Populate typed question display and trigger AI tutor turn
    setTypedQuestion(transcript);

    if (language === 'indic-auto' && detectedLang && detectedLang !== 'indic-auto') {
      setLanguage(detectedLang);
    }

    await executeTurn('ask', transcript, detectedLang || language);
  }, [language, executeTurn]);

  const handleVoiceError = useCallback((errMessage) => {
    setIsRecording(false);
    setTutorStatus('ready');
    console.warn('Voice Recording Error:', errMessage);
  }, []);

  // Keyboard shortcut: Enter to submit question
  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeTurn('ask');
    }
  };

  return (
    <div className="workspace-root">
      {/* Top Application Header */}
      <Header
        subject={subject}
        onSubjectChange={setSubject}
        language={language}
        onLanguageChange={setLanguage}
        tutorStatus={tutorStatus}
        backendConnected={backendConnected}
        onNewSession={handleNewSession}
        inputSource={inputSource}
        onInputSourceChange={handleInputSourceChange}
      />

      {/* Device Voice Fallback Toast Pill (Milestone 7) */}
      {deviceVoiceNotice && (
        <div className="device-voice-toast" role="status" aria-live="polite">
          🔊 Using device speech (API rate limit / offline)
        </div>
      )}

      {/* Mobile Segmented Switch (< 768px) */}
      <div className="mobile-tab-bar" role="tablist" aria-label="Mobile workspace switch">
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'whiteboard'}
          className={`mobile-tab-btn ${mobileTab === 'whiteboard' ? 'mobile-tab-active' : ''}`}
          onClick={() => setMobileTab('whiteboard')}
        >
          {inputSource === 'pdf' ? '📄 PDF Worksheet' : '✏️ Whiteboard'}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'tutor'}
          className={`mobile-tab-btn ${mobileTab === 'tutor' ? 'mobile-tab-active' : ''}`}
          onClick={() => setMobileTab('tutor')}
        >
          🤖 Tutor Chat {messages.length > 0 && `(${messages.length})`}
        </button>
      </div>

      {/* Main Responsive Two-Column Workspace */}
      <main className="workspace-body">
        {/* Left Column: Unified Two-Layer Digital Whiteboard & Document Workspace */}
        <section
          className={`workspace-col whiteboard-col ${mobileTab !== 'whiteboard' ? 'mobile-hidden' : ''}`}
          aria-label={inputSource === 'pdf' ? 'PDF Worksheet' : 'Student Whiteboard'}
        >
          <Whiteboard
            ref={whiteboardRef}
            onSnapshotGenerated={(snapshot) => {
              setLatestSnapshot(snapshot);
              if (snapshot?.hasPdf) {
                setInputSource('pdf');
              }
            }}
            onDemoPresetLoaded={handleDemoPresetLoaded}
          />
        </section>

        {/* Right Column: AI Tutor Conversation & Feedback Panel */}
        <section
          className={`workspace-col tutor-col ${mobileTab !== 'tutor' ? 'mobile-hidden' : ''}`}
          aria-label="Tutor Feedback and History"
        >
          <TutorPanel
            messages={messages}
            onQuickAction={handleQuickAction}
            subject={subject}
            language={language}
            latestSnapshot={latestSnapshot}
            isTutorThinking={isTutorThinking}
            tutorStatus={tutorStatus}
            autoSpeak={autoSpeak}
            onToggleAutoSpeak={() => setAutoSpeak((prev) => !prev)}
            onPlayAudio={handlePlayAudio}
            onStopAudio={handleStopAudio}
            currentlyPlayingMsgId={currentlyPlayingMsgId}
            audioLoadingMsgId={audioLoadingMsgId}
          />
        </section>
      </main>

      {/* Fixed Bottom Action Bar */}
      <footer className="workspace-bottom-bar">
        <div className="bottom-bar-inner">
          {/* Voice Input Button */}
          <VoiceButton
            isRecording={isRecording}
            onRecordingStart={handleVoiceRecordStart}
            onRecordingComplete={handleVoiceRecordComplete}
            onError={handleVoiceError}
            disabled={isTutorThinking}
          />

          {/* Quick PDF switch shortcut button */}
          <button
            type="button"
            className={`pdf-mode-toggle-btn ${inputSource === 'pdf' ? 'pdf-active' : ''}`}
            onClick={() => handleInputSourceChange(inputSource === 'whiteboard' ? 'pdf' : 'whiteboard')}
            title={inputSource === 'pdf' ? 'Switch back to Whiteboard' : 'Upload or inspect PDF worksheet (Section 6)'}
            aria-label="Toggle PDF Worksheet Mode"
          >
            <span>{inputSource === 'pdf' ? '✏️ Board' : '📄 PDF'}</span>
          </button>

          {/* Text Input Box */}
          <div className="input-field-wrapper">
            <input
              type="text"
              className="typed-question-input"
              placeholder={
                isRecording
                  ? 'Listening to your voice...'
                  : tutorStatus === 'transcribing'
                  ? 'Transcribing your question...'
                  : tutorStatus === 'checking'
                  ? 'Verifying step with SymPy CAS...'
                  : tutorStatus === 'speaking'
                  ? 'Tutor is speaking answer...'
                  : inputSource === 'pdf'
                  ? 'Ask about this PDF page... (e.g. Can you explain question 1?)'
                  : 'Type a question or step... (e.g. Is my step right?)'
              }
              value={typedQuestion}
              onChange={(e) => setTypedQuestion(e.target.value)}
              onKeyDown={handleInputKeyDown}
              disabled={isRecording || isTutorThinking}
              aria-label="Student question input"
            />
          </div>

          {/* Submit / Ask Button */}
          <button
            type="button"
            className="btn-ask-tutor"
            onClick={() => executeTurn('ask')}
            disabled={isTutorThinking || isRecording}
            title="Send your question and workspace snapshot to AI Tutor"
            aria-label="Ask AI Tutor"
          >
            <span className="btn-ask-label">Ask Tutor</span>
            <svg className="btn-ask-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </footer>
    </div>
  );
}
