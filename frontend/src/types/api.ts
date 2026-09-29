/**
 * 后端接口的类型定义。
 *
 * 与 FastAPI 的返回结构一一对应（见 backend/app/services/meme/query.py）。
 * 前端不自己算热度、不自己判生命周期，只做展示。
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
/** 认证强度标签：准入是并集（任一 UP 介绍过就入池），标签仍区分谁做过 */
export type CertLabel = "双 UP 认证" | "梗百科认证" | "梗指南认证" | "未认证";

export interface Transparency {
  data_platform: string;
  certification: string[];
  /** 准入规则原文（并集 / 认证窗口天数），设置页与详情页据此说明 */
  certification_rule?: string;
  cert_window_days?: number;
  /** 热榜的"活着"门槛说明（过气不出榜 + 天数/近7天播放二选一） */
  board_gate?: string;
  board_gate_on?: boolean;
  hotness_algorithm: string;
  /** 真实采集的抽样口径说明 */
  sampling?: string;
  /** 观测闸门：接口空返回怎么记、观测不足时为什么拒绝给趋势结论 */
  coverage_rule?: string;
  /** 梗介绍四档来源与「不改写」的约定 */
  intro_rule?: string;
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

export interface RefreshStatus extends RefreshInfo {
  running: boolean;
  trigger?: string;
  started_at?: string;
  data_source?: string;
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
  /** data_through 距今天几天；0 表示已含今天 */
  data_lag_days: number | null;
  certified_count: number;
  /** 梗库总数（过了准入且有快照），热榜数 = certified_count ≤ 这个数 */
  library_count?: number;
  /** 因"活着"门槛没上热榜的梗数 */
  gated_out?: number;
  /** 两位 UP 主都没介绍过的梗数（发现层并集之外，只能在梗管理里看到） */
  candidate_count: number;
  source_breakdown: Partial<Record<DataSource, number>>;
  window_days: number;
  filters: { key: HomeFilter; label: string }[];
  lifecycle_stages: { key: LifecycleStage; label: string; emoji: string }[];
  transparency: Transparency;
  /** 自动/手动刷新的状态；老版本后端可能没有 */
  refresh?: RefreshInfo;
}

export interface Thumbnail {
  emoji: string;
  color: string;
  /** 真实封面（人工挑的或 B 站视频封面）；为空则退回表情贴纸 */
  image?: string;
  /** true 表示这张封面是人工维护的，不是某条视频自动带出来的 */
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
   *  所以那几个增长百分比必须先说清是几天算出来的，否则没法分辨真跌和抖动。 */
  observed_days: number | null;
  observed_window_days: number | null;
  coverage: number | null;
  prev_observed_days: number | null;
  thumbnail: Thumbnail;
  /** 这个梗自己的数据来源（真实采集和演示数据可能混在同一个库里） */
  meme_data_source: DataSource;
  /** 在线核验状态：证据是不是真从 B 站投稿里抓到的 */
  verification_state: "verified_both" | "partially_verified" | "unverified";
  /** 认证强度标签：准入看并集（任一 UP 介绍过），标签仍区分双 UP / 单 UP */
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
  /** board=过了"活着"门槛的热榜；all=完整梗库 */
  scope?: "board" | "all";
  /** 梗库总数（未过门槛前）*/
  library_total?: number;
  /** 被上榜门槛挡掉的数量 */
  gated_out?: number;
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
  /** 只有真实抓取到的投稿才允许渲染成可点开的链接 */
  linkable?: boolean;
}

export interface Certification {
  encyclopedia: CertificationSide;
  guide: CertificationSide;
  /** 双 UP 徽章：两位都独立介绍过（交集） */
  certified: boolean;
  /** 发现层准入：任一 UP 介绍过（并集） */
  admitted: boolean;
  certified_by: string[];
  cert_label: CertLabel;
  /** 认证证据看的是最近多少天（滚动窗口） */
  cert_window_days: number;
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
  /** B 站「综合排序」（搜这个词看到的默认顺序）里的名次；null = 不在抓到的那一页里 */
  search_rank?: number | null;
  data_source: DataSource;
}

export interface TrendPoint {
  date: string;
  hotness: number;
  view: number;
  discussion: number;
  video_count: number;
  creator_count: number;
  /** false = 这天接口给了个空壳，画图上必须跟"真的是 0"分开 */
  observed?: boolean;
}

export interface Trend {
  window: number;
  /** 窗口里真正观测到的天数与覆盖度 */
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

/** 介绍来源：人工撰写 / 字幕原文摘录 / 由真实证据原文拼出 / 什么都没有 */
export type IntroSource = "manual" | "transcript" | "evidence" | "none";

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

/** AI 浓缩版介绍：只能是字幕原文句子的子集，逐字校验过才敢给前端 */
export interface IntroSummary {
  text: string;
  /** 被选中照抄的原文句子，顺序就是原文顺序 */
  sentences: string[];
  /** 模型想加但原文没有的话，留着当证据，界面不显示 */
  invented: string[];
  chars: number;
  source: "llm" | "cache" | "rule";
  model: string;
  data_version: string;
  generated_at: string | null;
  verified: boolean;
}

/** 解说视频字幕原文：正文只放挑出来的那几句，折叠区给可对照的原文 */
export interface IntroTranscript {
  bvid: string;
  video_title: string;
  url: string;
  /** cc = UP 主/字幕组上传的人工字幕，ai = B 站自动识别，错字明显更多 */
  kind: "cc" | "ai";
  kind_label: string;
  kind_hint: string;
  role: string;
  up_label: string;
  /** 这条字幕来自双 UP 认证的解说视频吗；不是的话界面要标出来 */
  certified: boolean;
  chars: number;
  excerpt: string;
  excerpt_chars: number;
  matched_sentences: number;
  full: string;
  full_truncated: boolean;
  fetched_at: string;
  /** 没生成过就是 null：页面继续用未缩短的规则摘录 */
  summary: IntroSummary | null;
}

export interface MemeIntro {
  text: string;
  source: IntroSource;
  source_label: string;
  note: string;
  evidence: IntroEvidence[];
  excerpt: IntroExcerpt | null;
  transcript: IntroTranscript | null;
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

/* ------------------------------ 梗管理（人工维护） ------------------------------ */

/** 管理列表的一行：正式梗与候选梗都在里面。 */
export interface ManageListItem {
  id: number;
  name: string;
  description: string;
  status: string;
  certified: boolean;
  /** 是否通过发现层准入（任一 UP 介绍过）——与 certified（双 UP 徽章）是两层 */
  admitted: boolean;
  cert_label: CertLabel;
  certified_by: string[];
  data_source: DataSource;
  verification_state: string;
  hotness: number | null;
  has_manual_cover: boolean;
  thumbnail: Thumbnail;
}

export interface ManageList {
  total: number;
  managed_count: number;
  /** 双 UP 认证的梗数（徽章口径，交集） */
  certified_count: number;
  /** 非双 UP 的梗数（含单 UP 入池的） */
  candidate_count: number;
  /** 入池梗数（并集准入） */
  in_pool_count: number;
  /** 两位 UP 都没介绍过的梗数 */
  out_of_pool_count: number;
  cert_window_days: number;
  items: ManageListItem[];
}

/** 可以挑来当封面的真实视频封面。 */
export interface CoverOption {
  cover: string;
  bvid: string;
  title: string;
  view: number;
  data_source: DataSource;
}

/** 梗管理里的"采信样本"：这些视频真的进了热度计算。 */
export interface SampleVideo {
  bvid: string;
  title: string;
  view: number;
  author: string;
  url: string;
  relevance_score: number;
  matched_terms: string[];
  data_source: DataSource;
}

export interface SampleVideos {
  accepted: number;
  views: number;
  items: SampleVideo[];
}

export interface ManageView {
  id: number;
  name: string;
  slug: string;
  description: string;
  aliases: string[];
  keywords: string[];
  cover_url: string;
  auto_cover: string;
  effective_cover: string;
  cover_options: CoverOption[];
  sample_videos: SampleVideos;
  data_source: DataSource;
  status: string;
  certified: boolean;
  admitted: boolean;
  cert_label: CertLabel;
  certified_by: string[];
  verification_state: string;
  card: MemeCard | null;
  note: string;
}

export interface MemeMetaPatch {
  cover_url?: string;
  description?: string;
  aliases?: string[];
  keywords?: string[];
}

export interface MemeMetaResult {
  changed: string[];
  meme: ManageView;
}
