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
  | "obsolete"
  /** 闸门态，不是阶段：近 7 天真正观测到的天数不够，算法拒绝给趋势结论 */
  | "insufficient";
export type CatchUpStatus = "can_catch" | "caution" | "too_late" | "insufficient";
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
  /** 观测闸门：接口空返回怎么记、观测不足时为什么拒绝给趋势结论 */
  coverage_rule?: string;
  lifecycle_algorithm: string;
  llm_role: string;
}

/** 上次刷新的摘要：这套数是几点、由谁、怎么刷出来的 */
export interface RefreshLast {
  at: string | null;
  trigger: string;
  mode: string;
  exit_code: number;
  collected: number | null;
  targets: number | null;
  failed: number | null;
  skipped_demo: number | null;
  data_through: string | null;
}

export interface RefreshSchedule {
  enabled: boolean;
  at: string;
  full_weekday: number;
  discovery: boolean;
  weekday_names?: string[];
}

export interface RefreshInfo {
  last: RefreshLast | null;
  schedule: RefreshSchedule;
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
  /** 自动/手动刷新状态；后端老版本可能没有 */
  refresh?: RefreshInfo;
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
  /** 近 N 天里真正观测到几天。B 站搜索会随机把有内容的日子返回成空壳，
   *  增长百分比必须先说清是几天算出来的，否则分不清真跌和接口抖动。 */
  observed_days?: number | null;
  observed_window_days?: number | null;
  coverage?: number | null;
  prev_observed_days?: number | null;
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
  /** B 站「综合排序」（搜这个词看到的默认顺序）里的名次；null = 不在抓到的那一页里 */
  search_rank?: number | null;
  data_source: DataSource;
}

export interface VideoList {
  total: number;
  items: VideoItem[];
  note?: string;
  /** 请求的排法与实际生效的排法——库里一条名次都没抓到时后端会退回播放量 */
  sort?: string;
  sort_applied?: string;
  sort_label?: string;
}

export interface TrendPoint {
  date: string;
  hotness: number;
  view: number;
  discussion: number;
  video_count: number;
  creator_count: number;
  /** false = 这天接口给了个空壳，柱子上必须跟"真的是 0"分开画 */
  observed?: boolean;
}

export interface Trend {
  window: number;
  observed_days?: number;
  coverage?: number;
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
