/**
 * Audio capture, WAV encoding, and playback utilities.
 * Encodes browser microphone audio directly into standard 16kHz 16-bit mono PCM .wav
 * so it is natively supported by Gnani Prisma v3.0 REST STT across all browsers.
 */

let activeAudioElement = null;

/**
 * Encodes a Float32Array of audio samples into a standard 16-bit mono PCM WAV Blob.
 * 
 * @param {Float32Array} samples - Normalized audio samples in [-1.0, 1.0]
 * @param {number} sampleRate - Target sample rate (default 16000 Hz)
 * @returns {Blob} - audio/wav Blob
 */
export function encodeWAV(samples, sampleRate = 16000) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const bytesPerSample = bitsPerSample / 8;
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  // Helper to write ASCII strings to DataView
  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  // RIFF Chunk Descriptor
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true); // ChunkSize
  writeString(8, 'WAVE');

  // "fmt " sub-chunk
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);             // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true);              // AudioFormat (1 = PCM)
  view.setUint16(22, numChannels, true);    // NumChannels (1 = Mono)
  view.setUint32(24, sampleRate, true);     // SampleRate (16000)
  view.setUint32(28, byteRate, true);       // ByteRate
  view.setUint16(32, blockAlign, true);     // BlockAlign
  view.setUint16(34, bitsPerSample, true);  // BitsPerSample (16)

  // "data" sub-chunk
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  // Write 16-bit PCM samples with clipping protection
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    const intSample = s < 0 ? s * 0x8000 : s * 0x7FFF;
    view.setInt16(offset, intSample, true);
  }

  return new Blob([view], { type: 'audio/wav' });
}

/**
 * Resamples an AudioBuffer to 16kHz mono using OfflineAudioContext.
 * 
 * @param {AudioBuffer} audioBuffer
 * @returns {Promise<Blob>}
 */
export async function convertTo16kHzWav(audioBuffer) {
  const targetSampleRate = 16000;
  const duration = audioBuffer.duration;
  const targetLength = Math.max(1, Math.ceil(duration * targetSampleRate));

  const OfflineCtxClass = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const offlineCtx = new OfflineCtxClass(1, targetLength, targetSampleRate);

  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineCtx.destination);
  source.start(0);

  const renderedBuffer = await offlineCtx.startRendering();
  const samples = renderedBuffer.getChannelData(0);

  return encodeWAV(samples, targetSampleRate);
}

/**
 * AudioRecorder class managing MediaStream lifecycle, timer enforcement, and WAV conversion.
 */
export class AudioRecorder {
  constructor(options = {}) {
    this.maxDurationSeconds = options.maxDurationSeconds || 25; // 25s hard stop (under Gnani 30s limit)
    this.onProgress = options.onProgress || null; // Callback for elapsed time (seconds)
    this.onAutoStop = options.onAutoStop || null; // Callback when max duration reached

    this.stream = null;
    this.mediaRecorder = null;
    this.chunks = [];
    this.startTime = 0;
    this.timerInterval = null;
    this.isRecording = false;
  }

  async start() {
    if (this.isRecording) return;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (err) {
      throw new Error(`Microphone permission denied or unavailable: ${err.message}`);
    }

    this.chunks = [];
    this.isRecording = true;
    this.startTime = Date.now();

    // Prefer common audio formats supported by browser MediaRecorder
    let mimeType = '';
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
    for (const cand of candidates) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(cand)) {
        mimeType = cand;
        break;
      }
    }

    this.mediaRecorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        this.chunks.push(e.data);
      }
    };

    this.mediaRecorder.start(200); // 200ms slice intervals

    // Track elapsed time & enforce hard stop at 25s
    this.timerInterval = setInterval(() => {
      const elapsed = (Date.now() - this.startTime) / 1000;
      if (this.onProgress) {
        this.onProgress(Math.min(this.maxDurationSeconds, elapsed));
      }

      if (elapsed >= this.maxDurationSeconds) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
        if (this.onAutoStop) {
          this.onAutoStop();
        }
      }
    }, 250);
  }

  async stop() {
    if (!this.isRecording) return null;
    this.isRecording = false;

    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }

    const elapsed = (Date.now() - this.startTime) / 1000;

    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) {
        this.cleanup();
        return resolve(null);
      }

      this.mediaRecorder.onstop = async () => {
        try {
          if (elapsed < 0.4) {
            this.cleanup();
            return reject(new Error('Audio recording too short (please speak for at least 0.5s).'));
          }

          const rawBlob = new Blob(this.chunks, { type: this.mediaRecorder.mimeType || 'audio/webm' });
          this.cleanup();

          // Decode raw audio and resample to 16kHz mono PCM WAV
          const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
          const audioCtx = new AudioCtxClass();
          const arrayBuffer = await rawBlob.arrayBuffer();
          const decodedBuffer = await audioCtx.decodeAudioData(arrayBuffer);
          await audioCtx.close();

          const wavBlob = await convertTo16kHzWav(decodedBuffer);
          resolve({ wavBlob, duration: elapsed });
        } catch (err) {
          this.cleanup();
          reject(new Error(`Failed to process recorded audio: ${err.message}`));
        }
      };

      try {
        this.mediaRecorder.stop();
      } catch {
        this.cleanup();
        resolve(null);
      }
    });
  }

  cleanup() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    this.mediaRecorder = null;
    this.chunks = [];
  }
}

/**
 * Plays a WAV Blob or raw audio URL through an HTMLAudioElement.
 * Automatically stops any previously playing audio and revokes Object URLs.
 * 
 * @param {Blob|string} audioSource - Blob or data URL / audio URL
 * @param {Function} [onStart]
 * @param {Function} [onEnd]
 * @param {Function} [onError]
 * @returns {HTMLAudioElement}
 */
export function playWavBlob(audioSource, onStart, onEnd, onError) {
  stopCurrentAudio();

  let url;
  let isBlob = false;

  if (audioSource instanceof Blob) {
    url = URL.createObjectURL(audioSource);
    isBlob = true;
  } else {
    url = audioSource;
  }

  const audio = new Audio(url);
  activeAudioElement = audio;

  const cleanup = () => {
    if (isBlob) {
      URL.revokeObjectURL(url);
    }
    if (activeAudioElement === audio) {
      activeAudioElement = null;
    }
  };

  audio.onplay = () => {
    if (onStart) onStart();
  };

  audio.onended = () => {
    cleanup();
    if (onEnd) onEnd();
  };

  audio.onerror = (e) => {
    cleanup();
    if (onError) onError(e);
  };

  audio.play().catch((err) => {
    cleanup();
    if (onError) onError(err);
  });

  return audio;
}

/**
 * Stops any actively playing audio (HTML5 audio or browser SpeechSynthesis).
 */
export function stopCurrentAudio() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
    } catch {}
  }
  if (activeAudioElement) {
    try {
      activeAudioElement.pause();
      activeAudioElement.currentTime = 0;
    } catch {
      // Safe ignore
    }
    activeAudioElement = null;
  }
}

/**
 * Speaks text using the browser's native SpeechSynthesis API as an offline/rate-limit fallback.
 * Automatically cleans text for natural speech pronunciation.
 * 
 * @param {string} text
 * @param {string} languageCode - Target locale e.g. 'en-IN', 'hi-IN', 'kn-IN', 'ta-IN', 'te-IN'
 * @param {Function} [onStart]
 * @param {Function} [onEnd]
 * @param {Function} [onError]
 * @returns {SpeechSynthesisUtterance|null}
 */
export function speakWithBrowserFallback(text, languageCode = 'en-IN', onStart, onEnd, onError) {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    if (onError) onError(new Error('SpeechSynthesis not supported in this browser'));
    return null;
  }

  stopCurrentAudio();

  // Strip markdown formatting for natural vocalization
  const clean = text
    .replace(/\*{1,3}(.*?)\*{1,3}/g, '$1')
    .replace(/`+(.*?)`+/g, '$1')
    .replace(/#+\s*/g, '')
    .replace(/\\\[(.*?)\\\]/g, '$1')
    .replace(/\\\((.*?)\\\)/g, '$1')
    .replace(/\$\$(.*?)\$\$/g, '$1')
    .replace(/\$(.*?)\$/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();

  if (!clean) {
    if (onEnd) onEnd();
    return null;
  }

  const utterance = new SpeechSynthesisUtterance(clean);
  const targetLang = (languageCode && languageCode !== 'indic-auto') ? languageCode : 'en-IN';
  utterance.lang = targetLang;
  utterance.rate = 0.95;

  utterance.onstart = () => {
    if (onStart) onStart();
  };

  utterance.onend = () => {
    if (onEnd) onEnd();
  };

  utterance.onerror = (e) => {
    console.warn('SpeechSynthesis error:', e);
    if (onError) onError(e);
  };

  window.speechSynthesis.speak(utterance);
  return utterance;
}

/**
 * Checks if an audio is currently playing.
 */
export function isAudioPlaying() {
  const isSpeechActive = typeof window !== 'undefined' && window.speechSynthesis && window.speechSynthesis.speaking;
  return (activeAudioElement !== null && !activeAudioElement.paused) || Boolean(isSpeechActive);
}


