/**
 * 后端接口的类型定义（小程序端）。
 *
 * 与 frontend/src/types/api.ts 同源，只留小程序会用到的部分；
 * 字段含义以 backend/app/services/meme/query.py 为准，
 * tests/contract.test.ts 会拿真实接口返回逐字段核对，防止两头漂移。
 */

export type DataSource = "mock" | "bilibili" | "mixed" | "pending";
export type LifecycleStage =
  | "sprouting"
  | "rising"
  | "explosive"
  | "plateau"
  | "receding"
  | "obsolete";
export type CatchUpStatus = "can_catch" | "caution" | "too_late";
export type HomeFilter = "all" | "hot" | "taking_off" | "receding";
export type CertLabel = "双 UP 认证" | "梗百科认证" | "梗指南认证" | "未认证";
export type IntroSource = "manual" | "evidence" | "none";

export interface Transparency {
  data_platform: string;
  certification: string[];
  certification_rule?: string;
  cert_window_days?: number;
  board_gate?: string;
  board_gate_on?: boolean;
  hotness_algorithm: string;
  sampling?: string;
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
  /** 序列里最后一个有数据的日期（采集窗口不含今天，所以通常是昨天） */
  data_through: string | null;
  data_lag_days: number | null;
  certified_count: number;
  library_count?: number;
  gated_out?: number;
  candidate_count: number;
  source_breakdown: Partial<Record<DataSource, number>>;
  window_days: number;
  filters: { key: HomeFilter; label: string }[];
  lifecycle_stages: { key: LifecycleStage; label: string; emoji: string }[];
  transparency: Transparency;
}

export interface Thumbnail {
  emoji: string;
  color: string;
  image?: string;
  manual?: boolean;
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
  meme_data_source: DataSource;
  verification_state: "verified_both" | "partially_verified" | "unverified";
  cert_label: CertLabel;
  certified_by: string[];
  double_certified: boolean;
  certified_at: string | null;
  data_updated_at: string | null;
}

export interface MemeList {
  filter: HomeFilter;
  filter_label: string;
  total: number;
  scope?: "board" | "all";
  library_total?: number;
  gated_out?: number;
  items: MemeCard[];
  data_source: DataSource;
  is_demo: boolean;
  window_days: number;
}

export interface Hotness {
  score: number;
  window_days: number;
  components: Record<string, number | undefined>;
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
  linkable?: boolean;
}

export interface Certification {
  encyclopedia: CertificationSide;
  guide: CertificationSide;
  certified: boolean;
  admitted: boolean;
  certified_by: string[];
  cert_label: CertLabel;
  cert_window_days: number;
  certified_at: string | null;
}

export interface IntroEvidence {
  role: string;
  up_label: string;
  up_name: string;
  video_title: string;
  bvid: string;
  video_url: string;
  published_at: string;
  verified: boolean;
}

export interface IntroExcerpt {
  text: string;
  video_title: string;
  author: string;
  bvid: string;
  url: string;
  data_source: DataSource;
}

export interface MemeIntro {
  text: string;
  source: IntroSource;
  source_label: string;
  note: string;
  evidence: IntroEvidence[];
  excerpt: IntroExcerpt | null;
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

export interface VideoList {
  total: number;
  items: VideoItem[];
  note?: string;
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
  intro: MemeIntro;
  videos: VideoItem[];
  trend: Trend;
  insight: InsightBundle;
}
