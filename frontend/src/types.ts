export type Language = 'es' | 'en' | 'zh';

export type ChunkStatus = 'pending' | 'uploading' | 'done' | 'error';

export interface ChunkInfo {
  index: number;
  status: ChunkStatus;
  error?: string;
}

export interface AgreementMetrics {
  lexical_similarity: number;
  length_ratio: number;
  confidence_hint: 'high' | 'medium' | 'low';
}

export interface Segment {
  segment_id: string;
  time_start: number;
  time_end: number;
  openai_asr_ko: string;
  soniox_asr_ko: string;
  reconstructed_ko: string;
  translated_text: string;
  target_language: Language;
  confidence: 'high' | 'medium' | 'low';
  uncertainties: string[];
  agreement: AgreementMetrics;
  revision_status: 'draft' | 'revised' | 'final';
  asr_sources?: string[];  // Which ASR models heard this: ["openai"], ["soniox"], or ["openai", "soniox"]
}

export interface ChunkResponse {
  chunk_index: number;
  status: string;
  segments: Segment[];
}
