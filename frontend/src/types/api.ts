/**
 * 后端接口的类型定义。
 *
 * 与 FastAPI 的返回结构一一对应（见 backend/app/services/meme/query.py）。
 * 前端不自己算热度、不自己判生命周期，只做展示。
 */

export type DataSource = "mock" | "bilibili";
export type LifecycleStage =
  | "sprouting"
  | "rising"
  | "explosive"
  | "plateau"
  | "receding"
  | "obsolete";
export type CatchUpStatus = "can_catch" | "caution" | "too_late";
export type HomeFilter = "all" | "hot" | "taking_off" | "receding";

export interface Transparency {
  data_platform: string;
  certification: string[];
  hotness_algorithm: string;
  lifecycle_algorithm: string;
  llm_role: string;
}

export interface Meta {
  app_name: string;
  version: string;
  environment: string;
  data_source: DataSource;
  is_demo: boolean;
  data_updated_at: string | null;
  certified_count: number;
  candidate_count: number;
  window_days: number;
  filters: { key: HomeFilter; label: string }[];
  lifecycle_stages: { key: LifecycleStage; label: string; emoji: string }[];
  transparency: Transparency;
}

export interface Thumbnail {
  emoji: string;
  color: string;
}

export interface MemeCard {
  id: number;
  name: string;
  slug: string;
  description: string;
  aliases: string[];
  keywords: string[];
  data_source: DataSource;
  hotness: number;
  stage: LifecycleStage;
  stage_label: string;
  nickname: string;
  emoji: string;
  discussion_growth: number | null;
  video_growth: number | null;
  creator_growth: number | null;
  catch_status: CatchUpStatus;
  catch_label: string;
  catch_reason: string;
  catch_confidence: number;
  thumbnail: Thumbnail;
  certified_at: string | null;
  data_updated_at: string | null;
}

export interface MemeList {
  filter: HomeFilter;
  filter_label: string;
  total: number;
  items: MemeCard[];
  data_source: DataSource;
  is_demo: boolean;
  window_days: number;
}

export interface HotnessComponents {
  view?: number;
  interaction?: number;
  content?: number;
  creator?: number;
  growth?: number;
  [key: string]: number | undefined;
}

export interface Hotness {
  score: number;
  window_days: number;
  components: HotnessComponents;
  weights: Record<string, number>;
}

export interface LifecycleStep {
  key: LifecycleStage;
  label: string;
  emoji: string;
  active: boolean;
}

export interface CatchUp {
  status: CatchUpStatus;
  label: string;
  reason?: string;
  confidence: number;
  decided_by: string;
}

export interface Lifecycle {
  stage: LifecycleStage;
  stage_label: string;
  emoji: string;
  indicators: Record<string, number | string | null>;
  reasons: string[];
  catch_up: CatchUp;
  computed_at: string | null;
  stages: LifecycleStep[];
}

export interface MetricPair {
  value: number;
  growth: number | null;
}

export interface Metrics {
  videos: MetricPair;
  creators: MetricPair;
  comments: MetricPair;
  danmaku: MetricPair;
  views: MetricPair;
  interactions: MetricPair;
  window_days: number;
  note: string;
}

export interface CertificationSide {
  up_name: string;
  up_mid?: number;
  bvid?: string;
  video_title?: string;
  video_url?: string;
  published_at?: string | null;
  confirmed: boolean;
  data_source?: string;
}

export interface Certification {
  encyclopedia: CertificationSide;
  guide: CertificationSide;
  certified: boolean;
  certified_at: string | null;
}

export interface VideoItem {
  bvid: string;
  title: string;
  author: string;
  url: string;
  cover: string;
  publish_time: string | null;
  view: number;
  like: number;
  coin: number;
  favorite: number;
  reply: number;
  danmaku: number;
  duration_seconds: number;
  duration_text: string;
  view_text: string;
  danmaku_text: string;
  relevance_score: number;
  data_source: DataSource;
}

export interface TrendPoint {
  date: string;
  hotness: number;
  view: number;
  discussion: number;
  video_count: number;
  creator_count: number;
}

export interface Trend {
  window: number;
  points: TrendPoint[];
}

export interface InsightRecord {
  kind: "trend_explanation" | "catch_up_advice";
  status: "ok" | "unavailable" | "error";
  available: boolean;
  source: "llm" | "rule" | "cache" | "none";
  model?: string;
  data_version: string;
  generated_at: string;
  error?: string;
  result: {
    text?: string;
    status?: CatchUpStatus;
    label?: string;
    reason?: string;
    confidence?: number;
  };
}

export interface InsightBundle {
  trend_explanation: InsightRecord | null;
  catch_up_advice: InsightRecord | null;
  algorithm_reason: string;
  catch_up: CatchUp;
}

export interface MemeDetail {
  meme: MemeCard;
  hotness: Hotness;
  lifecycle: Lifecycle;
  metrics: Metrics;
  certification: Certification;
  videos: VideoItem[];
  trend: Trend;
  insight: InsightBundle;
}

export interface LLMConfigView {
  provider: string;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  timeout_ms: number;
  max_retries: number;
  api_key_set: boolean;
  api_key_masked: string;
}

export interface SettingsView {
  config: LLMConfigView;
  data_source: DataSource;
  environment: string;
  version: string;
  allow_rule_fallback: boolean;
  env_file: string;
}

export interface LLMTestResult {
  ok: boolean;
  configured: boolean;
  message: string;
  model?: string;
  latency_ms?: number;
  echo?: string;
  kind?: string;
  config: LLMConfigView;
}

export interface SaveLLMResult {
  saved: boolean;
  persisted: boolean;
  written_keys: string[];
  api_key_updated: boolean;
  config: LLMConfigView;
}
