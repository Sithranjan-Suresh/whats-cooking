// Mirrors contract.md. Keep in sync with backend/app/serializers.py.

export type Angle = "top_seller" | "rising" | "slow_mover";
export type StageName = "analyze" | "script" | "visuals" | "voice" | "assemble";
export type StageStatus = "pending" | "running" | "done" | "failed" | "skipped";
export type JobStatus = "queued" | "running" | "needs_dish" | "done" | "failed";
export type Style = "bold" | "warm" | "minimal";
export type Privacy = "private" | "unlisted" | "public";

export interface ApiErrorBody {
  error: { code: string; message: string; retryable: boolean };
}

export interface Health {
  ok: boolean;
  mock: boolean;
  demo: boolean;
  actor: "owner" | "demo";
  veo_model: string;
  gemini_model: string;
  gemini_configured: boolean;
  youtube_configured: boolean;
}

export interface Restaurant {
  id: number;
  name: string;
  slug: string;
  logo_asset_id: number | null;
  logo_url: string | null;
  color_primary: string;
  color_accent: string;
  voice_tone: "friendly" | "upbeat" | "elegant";
  tts_voice: string;
  menu_count: number;
  has_sales: boolean;
  youtube_connected: boolean;
  youtube_configured?: boolean;
  youtube_channel_title: string | null;
  voices: { id: string; label: string }[];
}

export interface MenuItem {
  id: number;
  name: string;
  price_cents: number | null;
  price: string | null;
  description: string | null;
  category: string | null;
  photo_asset_id: number | null;
  photo_url: string | null;
}

export interface InsightCard {
  id: number;
  angle: Angle;
  menu_item: { id: number; name: string; price: string | null; photo_url: string | null };
  metric: { qty_7d?: number; qty_prev_7d?: number; wow_pct?: number; qty_14d?: number };
  metric_label: string;
  reason: string;
  reason_source: "gemini" | "rule";
}

export interface InsightsResponse {
  batch_id: string | null;
  cards: InsightCard[];
}

export interface SalesImportResult {
  rows: number;
  dropped: number;
  date_from: string;
  date_to: string;
  days: number;
  unmatched_items: string[];
}

export interface SalesSummary {
  rows: number;
  date_from: string | null;
  date_to: string | null;
  days?: number;
  unmatched_items: string[];
}

export interface Stage {
  name: StageName;
  status: StageStatus;
  started_at: string | null;
  ended_at: string | null;
  note: string | null;
}

export interface Beat {
  caption: string;
  seconds: number;
  facts?: ("name" | "price" | "description")[];
}

export interface Script {
  hook: string;
  beats: Beat[];
  voiceover: string;
  veo_prompt: string;
  title: string;
  description: string;
  hashtags: string[];
  facts_used: { field: string; value: string }[];
  source?: "gemini" | "gemini_repaired" | "template" | "edited";
}

export interface Analyze {
  is_food?: boolean;
  dish_guess?: string;
  menu_item_id?: number | null;
  confidence?: number;
  visual_notes?: string;
  quality?: string;
  reason?: "not_food" | "low_confidence" | "analyze_failed";
  warning?: string | null;
  candidates: MenuItem[];
}

export interface Job {
  id: number;
  status: JobStatus;
  mode: "photo" | "insight" | "menu";
  angle: Angle | null;
  style: Style;
  length_s: 8 | 15 | 30;
  veo_requested: boolean;
  stages: Stage[];
  analyze: Analyze | null;
  script: Script | null;
  menu_item: MenuItem | null;
  photo_url: string | null;
  veo_used: boolean;
  fallback_reason: string | null;
  flags: Record<string, boolean>;
  video: { id: number; url: string; poster_url: string | null } | null;
  cost_cents: number;
  error: string | null;
  error_stage: StageName | null;
  created_at: string;
  finished_at: string | null;
}

export interface Video {
  id: number;
  job_id: number | null;
  url: string;
  poster_url: string | null;
  dish: string | null;
  menu_item_id: number | null;
  duration_s: number;
  width: number;
  height: number;
  bytes: number;
  mode: "veo" | "free";
  cost_cents: number;
  title: string | null;
  description: string | null;
  hashtags: string[];
  youtube_id: string | null;
  youtube_url: string | null;
  youtube_privacy: Privacy | null;
  publish_status: "draft" | "publishing" | "published" | "failed";
  publish_error: string | null;
  publish_progress: number;
  created_at: string;
}

export interface Usage {
  today: { clips: number; limit: number };
  month: { est_cents: number; cap_cents: number };
  cost_per_sec_cents: number;
  free_mode: boolean;
  veo: { allowed: boolean; reason: string | null; message: string | null; est_cents: number };
}

export interface AppSettings {
  restaurant_id: number;
  daily_veo_clip_limit: number;
  monthly_cap_cents: number;
  free_mode: boolean;
  veo_cost_per_sec_cents: number;
}
