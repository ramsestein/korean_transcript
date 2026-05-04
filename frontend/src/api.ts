import type { Language, ChunkResponse } from './types';

function getHeaders(token: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (token && token !== 'disabled') {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function startSession(token: string, language: Language, prompt: string, chunkSeconds = 15): Promise<string> {
  const res = await fetch('/api/session/start', {
    method: 'POST',
    headers: { ...getHeaders(token), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      target_language: language,
      meeting_prompt: prompt,
      chunk_seconds: chunkSeconds,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(`Session start failed: ${err.detail || res.status}`);
  }
  const data = await res.json();
  return data.session_id as string;
}

export async function uploadChunk(
  token: string,
  sessionId: string,
  index: number,
  audio: Blob,
  startTime: number,
  endTime: number
): Promise<ChunkResponse> {
  const form = new FormData();
  const ext = audio.type.includes('mp4') ? 'mp4' : audio.type.includes('ogg') ? 'ogg' : 'webm';
  form.append('audio', audio, `chunk_${index}.${ext}`);
  form.append('chunk_index', String(index));
  form.append('local_start_time', String(startTime));
  form.append('local_end_time', String(endTime));

  const res = await fetch(`/api/session/${sessionId}/chunk`, {
    method: 'POST',
    headers: getHeaders(token),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(`Chunk ${index} failed: ${err.detail || res.status}`);
  }
  return res.json() as Promise<ChunkResponse>;
}

export async function uploadImages(
  token: string,
  sessionId: string,
  files: File[]
): Promise<{ image_ids: string[]; extracted: object[] }> {
  const form = new FormData();
  files.forEach(f => form.append('images', f));
  const res = await fetch(`/api/session/${sessionId}/context/images`, {
    method: 'POST',
    headers: getHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error(`Image upload failed: ${res.status}`);
  return res.json();
}

export async function generateSummary(token: string, sessionId: string): Promise<string> {
  const res = await fetch(`/api/session/${sessionId}/summary`, {
    method: 'POST',
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error(`Summary generation failed: ${res.status}`);
  const data = await res.json();
  return data.download_url as string;
}

export async function deleteSession(token: string, sessionId: string): Promise<void> {
  await fetch(`/api/session/${sessionId}`, {
    method: 'DELETE',
    headers: getHeaders(token),
  });
}
