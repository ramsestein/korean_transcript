import { uploadChunk } from './api';
import type { ChunkInfo } from './types';

export type OnChunkUpdate = (chunk: ChunkInfo) => void;

export class ChunkRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunkIndex = 0;
  private sessionId = '';
  private sessionStart = 0;
  private onUpdate: OnChunkUpdate = () => {};
  private chunkSeconds = 15;

  async start(sessionId: string, chunkSeconds: number, onUpdate: OnChunkUpdate): Promise<void> {
    this.sessionId = sessionId;
    this.sessionStart = Date.now();
    this.chunkIndex = 0;
    this.onUpdate = onUpdate;
    this.chunkSeconds = chunkSeconds;

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        channelCount: 1,
        sampleRate: 16000,
      },
    });

    const mimeType = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/ogg',
    ].find(t => MediaRecorder.isTypeSupported(t)) ?? '';

    this.mediaRecorder = new MediaRecorder(
      this.stream,
      mimeType ? { mimeType } : {}
    );

    this.mediaRecorder.addEventListener('dataavailable', (e: BlobEvent) => {
      if (e.data.size > 0) {
        const idx = this.chunkIndex++;
        const elapsed = (Date.now() - this.sessionStart) / 1000;
        const chunkStart = Math.max(0, elapsed - chunkSeconds);
        const chunkEnd = elapsed;
        void this.processChunk(idx, e.data, chunkStart, chunkEnd);
      }
    });

    // timeslice fires dataavailable automatically every chunkSeconds*1000 ms
    this.mediaRecorder.start(chunkSeconds * 1000);
  }

  private async processChunk(idx: number, blob: Blob, start: number, end: number): Promise<void> {
    this.onUpdate({ index: idx, status: 'uploading' });
    try {
      await uploadChunk(this.sessionId, idx, blob, start, end);
      this.onUpdate({ index: idx, status: 'done' });
    } catch (err) {
      // retry once after 2s
      try {
        await new Promise(r => setTimeout(r, 2000));
        await uploadChunk(this.sessionId, idx, blob, start, end);
        this.onUpdate({ index: idx, status: 'done' });
      } catch (err2) {
        this.onUpdate({ index: idx, status: 'error', error: String(err2) });
      }
    }
  }

  stop(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    this.stream?.getTracks().forEach(t => t.stop());
  }

  get isRecording(): boolean {
    return this.mediaRecorder?.state === 'recording';
  }
}
