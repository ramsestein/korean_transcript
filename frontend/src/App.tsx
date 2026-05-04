import { useState, useRef, useEffect, useCallback } from 'react';
import { ChunkRecorder } from './recorder';
import { startSession, generateSummary, deleteSession, uploadImages, uploadChunk } from './api';
import { Login } from './Login';
import { getAuthToken, setAuthToken, clearAuthToken } from './cookies';
import type { Language, ChunkInfo, Segment, ChunkResponse } from './types';
import './styles.css';

type Phase = 'setup' | 'recording' | 'done';

type LivePhoto = {
  id: string;
  preview: string;
  status: 'uploading' | 'done' | 'error';
  error?: string;
};

const LANG_LABELS: Record<Language, string> = { es: '🇪🇸 Spanish', en: '🇬🇧 English', zh: '🇨🇳 Chinese' };
const CHUNK_SECONDS = 15;

function fmt(s: number): string {
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const sec = Math.floor(s % 60).toString().padStart(2, '0');
  return `${m}:${sec}`;
}

export default function App() {
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [username, setUsername] = useState<string>('');
  const [phase, setPhase] = useState<Phase>('setup');
  const [language, setLanguage] = useState<Language | null>(null);
  const [meetingPrompt, setMeetingPrompt] = useState('');
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<ChunkInfo[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [summaryUrl, setSummaryUrl] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [livePhotos, setLivePhotos] = useState<LivePhoto[]>([]);

  const recorderRef = useRef<ChunkRecorder | PatchedRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const segmentMapRef = useRef<Map<string, Segment>>(new Map());

  const onChunkUpdate = useCallback((chunk: ChunkInfo) => {
    setChunks(prev => {
      const next = [...prev];
      const idx = next.findIndex(c => c.index === chunk.index);
      if (idx >= 0) next[idx] = chunk;
      else next.push(chunk);
      return next;
    });
  }, []);

  const handleNewSegments = useCallback((newSegs: Segment[]) => {
    newSegs.forEach(s => segmentMapRef.current.set(s.segment_id, s));
    const sorted = Array.from(segmentMapRef.current.values())
      .sort((a, b) => a.time_start - b.time_start);
    setSegments(sorted);
  }, []);

  // Expose handleNewSegments to recorder via api override
  useEffect(() => {
    // Patch uploadChunk to intercept segments
    const origUpload = (window as unknown as Record<string, unknown>)['__uploadPatch'];
    void origUpload;
  }, [handleNewSegments]);

  const handleLogout = useCallback(() => {
    clearAuthToken();
    setToken(null);
    setUsername('');
    window.location.reload();
  }, []);

  const handleStart = useCallback(async () => {
    if (!language || !token) return;
    setError(null);
    try {
      const sid = await startSession(token, language, meetingPrompt, CHUNK_SECONDS);
      setSessionId(sid);

      // Upload images if any
      if (imageFiles.length > 0) {
        await uploadImages(token, sid, imageFiles).catch(e => console.warn('Image upload:', e));
      }

      const recorder = new ChunkRecorder();
      recorderRef.current = recorder;

      // Wrap onChunkUpdate to also capture segments from response
      const patchedUpload = async (chunk: ChunkInfo & { _resp?: unknown }) => {
        onChunkUpdate(chunk);
        if (chunk._resp) {
          const resp = chunk._resp as { segments?: Segment[] };
          if (resp.segments) handleNewSegments(resp.segments);
        }
      };
      void patchedUpload;

      // We patch the uploadChunk inside recorder by subclassing
      const patchedRecorder = new PatchedRecorder(sid, token, handleNewSegments);
      recorderRef.current = patchedRecorder;
      await patchedRecorder.start(sid, token, CHUNK_SECONDS, onChunkUpdate);

      setPhase('recording');
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } catch (e) {
      setError(String(e));
    }
  }, [language, meetingPrompt, imageFiles, token, onChunkUpdate, handleNewSegments]);

  const handleStop = useCallback(async () => {
    recorderRef.current?.stop();
    if (timerRef.current) clearInterval(timerRef.current);
    setPhase('done');
  }, []);

  const handleSummary = useCallback(async () => {
    if (!sessionId || !token) return;
    setSummaryLoading(true);
    try {
      const url = await generateSummary(token, sessionId);
      setSummaryUrl(url);
    } catch (e) {
      setError(String(e));
    } finally {
      setSummaryLoading(false);
    }
  }, [sessionId, token]);

  const handleLivePhoto = useCallback(async (file: File) => {
    if (!sessionId || !token) return;
    const id = `${Date.now()}-${file.name}`;
    const preview = URL.createObjectURL(file);
    setLivePhotos(prev => [...prev, { id, preview, status: 'uploading' }]);
    try {
      await uploadImages(token, sessionId, [file]);
      setLivePhotos(prev => prev.map(p => p.id === id ? { ...p, status: 'done' } : p));
    } catch (e) {
      setLivePhotos(prev => prev.map(p => p.id === id ? { ...p, status: 'error', error: String(e) } : p));
    }
  }, [sessionId, token]);

  const handleLoginSuccess = useCallback((newToken: string, newUsername: string) => {
    console.log('App: login success', newUsername);
    setToken(newToken);
    setUsername(newUsername);
    setAuthToken(newToken);
  }, []);

  const handleEnd = useCallback(async () => {
    if (!sessionId || !token) return;
    await deleteSession(token, sessionId);
    setPhase('setup');
    setSessionId(null);
    setChunks([]);
    setSegments([]);
    setSummaryUrl(null);
    setError(null);
    setElapsed(0);
    setLanguage(null);
    setMeetingPrompt('');
    setImageFiles([]);
    setLivePhotos([]);
    livePhotos.forEach(p => URL.revokeObjectURL(p.preview));
    segmentMapRef.current.clear();
  }, [sessionId, livePhotos, token]);

  // Show login if no token
  if (!token) {
    return <Login onLogin={handleLoginSuccess} />;
  }

  return (
    <div className="app">
      <div className="header-row">
        <div>
          <h1>🇰🇷 Korean Meeting Interpreter</h1>
          <p className="subtitle">Real-time Korean transcription &amp; translation</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          {username && <span style={{ color: 'var(--text2)', marginRight: 12 }}>👤 {username}</span>}
          <button className="btn-secondary" onClick={handleLogout}>Logout</button>
        </div>
      </div>

      {error && (
        <div className="error-banner">⚠ {error} <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', color: 'inherit', padding: '0 4px', minHeight: 'auto' }}>✕</button></div>
      )}

      {phase === 'setup' && (
        <SetupPanel
          language={language}
          setLanguage={setLanguage}
          meetingPrompt={meetingPrompt}
          setMeetingPrompt={setMeetingPrompt}
          imageFiles={imageFiles}
          setImageFiles={setImageFiles}
          onStart={handleStart}
        />
      )}

      {phase === 'recording' && (
        <>
          <div className="card">
            <div className="rec-indicator">
              <div className="rec-dot" />
              <span className="rec-text">Recording — auto-uploading every {CHUNK_SECONDS}s</span>
              <span className="rec-timer">{fmt(elapsed)}</span>
            </div>
            <div className="btn-row" style={{ marginTop: 12 }}>
              <button className="btn-danger" onClick={handleStop}>⏹ Stop Recording</button>
              <PhotoCapture onPhoto={handleLivePhoto} />
            </div>
          </div>

          {livePhotos.length > 0 && (
            <div className="card">
              <h2>Context Photos ({livePhotos.length})</h2>
              <div className="photo-strip">
                {livePhotos.map(p => (
                  <div key={p.id} className={`photo-thumb photo-thumb-${p.status}`}>
                    <img src={p.preview} alt="context" />
                    <div className="photo-status">
                      {p.status === 'uploading' && <span className="spinner" />}
                      {p.status === 'done' && '✓'}
                      {p.status === 'error' && '✕'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {chunks.length > 0 && (
            <div className="card">
              <h2>Chunks ({chunks.length})</h2>
              <div className="chunk-list">
                {[...chunks].reverse().map(c => (
                  <div className="chunk-item" key={c.index}>
                    <div className={`dot dot-${c.status}`} />
                    <span>Chunk #{c.index + 1}</span>
                    <span style={{ marginLeft: 'auto', color: 'var(--text2)', fontSize: '0.75rem' }}>
                      {c.status === 'uploading' ? <span className="spinner" /> : c.status}
                    </span>
                    {c.error && <span style={{ color: 'var(--red)', fontSize: '0.72rem' }}>{c.error}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <TranscriptPanel segments={segments} />
        </>
      )}

      {phase === 'done' && (
        <>
          <TranscriptPanel segments={segments} />
          <div className="card">
            <h2>Session Complete</h2>
            {!summaryUrl ? (
              <button className="btn-primary" onClick={handleSummary} disabled={summaryLoading}>
                {summaryLoading ? <><span className="spinner" /> Generating…</> : '📄 Generate Operational Summary'}
              </button>
            ) : (
              <a className="summary-url" href={summaryUrl} download="summary.md">⬇ Download summary.md</a>
            )}
            <div style={{ marginTop: 10 }}>
              <button className="btn-secondary" onClick={handleEnd} style={{ width: '100%' }}>🔄 New Session</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// --- SetupPanel ---
function SetupPanel({
  language, setLanguage, meetingPrompt, setMeetingPrompt,
  imageFiles, setImageFiles, onStart
}: {
  language: Language | null;
  setLanguage: (l: Language) => void;
  meetingPrompt: string;
  setMeetingPrompt: (s: string) => void;
  imageFiles: File[];
  setImageFiles: (f: File[]) => void;
  onStart: () => void;
}) {
  return (
    <>
      <div className="card">
        <h2>Target Language</h2>
        <div className="lang-selector">
          {(['es', 'en', 'zh'] as Language[]).map(l => (
            <button key={l} className={`lang-btn ${language === l ? 'active' : ''}`} onClick={() => setLanguage(l)}>
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Meeting Context</h2>
        <label htmlFor="prompt">Optional: describe the meeting topic, participants, terminology</label>
        <textarea
          id="prompt"
          value={meetingPrompt}
          onChange={e => setMeetingPrompt(e.target.value)}
          placeholder="e.g. Collaboration meeting on MIMIC-IV dataset analysis with Dr. Kim from Seoul National University"
        />
      </div>

      <div className="card">
        <h2>Context Images (optional)</h2>
        <label className="file-label" htmlFor="images">
          {imageFiles.length > 0
            ? `${imageFiles.length} image(s) selected`
            : '📎 Upload slide images or documents'}
        </label>
        <input
          id="images"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          onChange={e => setImageFiles(Array.from(e.target.files ?? []))}
        />
      </div>

      <button className="btn-primary" disabled={!language} onClick={onStart}>
        🎙 Start Recording
      </button>
    </>
  );
}

// --- TranscriptPanel ---
function TranscriptPanel({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) return null;
  return (
    <div className="card">
      <h2>Transcript ({segments.length} segments)</h2>
      <div className="segment-list">
        {[...segments].reverse().map(seg => (
          <div key={seg.segment_id} className={`segment ${seg.revision_status}`}>
            <div className="segment-ko">{seg.reconstructed_ko}</div>
            <div className="segment-tr">{seg.translated_text}</div>
            <div className="segment-meta">
              <span className={`badge badge-${seg.confidence}`}>{seg.confidence}</span>
              <span className={`badge badge-${seg.revision_status}`}>{seg.revision_status}</span>
              <span className="segment-time">{fmt(seg.time_start)}–{fmt(seg.time_end)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- PhotoCapture ---
function PhotoCapture({ onPhoto }: { onPhoto: (f: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <button
        className="btn-outline"
        type="button"
        onClick={() => inputRef.current?.click()}
        title="Capture or upload an image to add context"
      >
        📷 Add Photo
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        capture="environment"
        style={{ display: 'none' }}
        onChange={e => {
          const file = e.target.files?.[0];
          if (file) { onPhoto(file); e.target.value = ''; }
        }}
      />
    </>
  );
}

// --- PatchedRecorder: standalone recorder to capture response segments ---

class PatchedRecorder {
  private sid: string;
  private token: string;
  private onSegs: (segs: Segment[]) => void;
  private _mr: MediaRecorder | null = null;
  private _stream: MediaStream | null = null;

  constructor(sid: string, token: string, onSegs: (segs: Segment[]) => void) {
    this.sid = sid;
    this.token = token;
    this.onSegs = onSegs;
  }

  async start(sessionId: string, token: string, chunkSeconds: number, onUpdate: (c: ChunkInfo) => void): Promise<void> {
    this.token = token;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1, sampleRate: 16000 },
    });

    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/mp4']
      .find(t => MediaRecorder.isTypeSupported(t)) ?? '';

    let chunkIndex = 0;
    const sessionStart = Date.now();
    let stopped = false;

    const upload = (blob: Blob, idx: number, start: number, end: number) => {
      onUpdate({ index: idx, status: 'uploading' });
      const attempt = (retries: number) => {
        uploadChunk(token, sessionId, idx, blob, start, end)
          .then((resp: ChunkResponse) => {
            onUpdate({ index: idx, status: 'done' });
            if (resp.segments?.length) this.onSegs(resp.segments);
          })
          .catch((err: unknown) => {
            if (retries > 0) {
              setTimeout(() => attempt(retries - 1), 2000);
            } else {
              onUpdate({ index: idx, status: 'error', error: String(err) });
            }
          });
      };
      attempt(1);
    };

    // Stop/restart approach: every chunkSeconds we stop the recorder,
    // which fires dataavailable with a COMPLETE valid audio blob (full header),
    // then immediately start a new recorder on the same stream.
    const cycle = () => {
      if (stopped) return;
      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      const idx = chunkIndex++;
      const chunkStart = (Date.now() - sessionStart) / 1000;

      mr.addEventListener('dataavailable', (e: BlobEvent) => {
        if (e.data.size > 0) {
          const chunkEnd = (Date.now() - sessionStart) / 1000;
          upload(e.data, idx, chunkStart, chunkEnd);
        }
      });

      mr.addEventListener('stop', () => {
        if (!stopped) cycle(); // start next chunk immediately
      });

      mr.start();
      setTimeout(() => {
        if (mr.state === 'recording') mr.stop();
      }, chunkSeconds * 1000);

      (this as unknown as { _mr: MediaRecorder })._mr = mr;
    };

    (this as unknown as { _stream: MediaStream })._stream = stream;
    (this as unknown as { _stopped: boolean | (() => void) })._stopped = () => { stopped = true; };

    cycle();
  }

  stop(): void {
    const stoppedFn = (this as unknown as { _stopped?: () => void })._stopped;
    if (typeof stoppedFn === 'function') stoppedFn();
    const mr = (this as unknown as { _mr?: MediaRecorder })._mr;
    const stream = (this as unknown as { _stream?: MediaStream })._stream;
    if (mr && mr.state !== 'inactive') mr.stop();
    stream?.getTracks().forEach(t => t.stop());
  }
}
