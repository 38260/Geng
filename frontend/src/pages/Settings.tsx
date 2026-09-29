import { useEffect, useState } from "react";

import { api } from "@/api/client";
import { EyeIcon, GearIcon, RefreshIcon } from "@/components/icons";
import { TransparencyFooter } from "@/components/Sections";
import { ErrorState } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useMeta } from "@/hooks/useAppData";
import type { LLMTestResult } from "@/types/api";

interface FormState {
  provider: string;
  base_url: string;
  model: string;
  temperature: string;
  max_tokens: string;
  api_key: string;
}

const PROVIDERS = [
  { value: "longcat", label: "LongCat" },
  { value: "openai-compatible", label: "OpenAI 兼容" },
];

export default function Settings() {
  const { meta } = useMeta();
  const { data, loading, error, reload } = useAsync(() => api.settings(), []);
  const [form, setForm] = useState<FormState | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [tone, setTone] = useState<"ok" | "bad" | "info">("info");
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [test, setTest] = useState<LLMTestResult | null>(null);

  useEffect(() => {
    if (!data) return;
    setForm({
      provider: data.config.provider,
      base_url: data.config.base_url,
      model: data.config.model,
      temperature: String(data.config.temperature),
      max_tokens: String(data.config.max_tokens),
      api_key: "",
    });
  }, [data]);

  const patch = (values: Partial<FormState>) => setForm((current) => ({ ...current!, ...values }));

  const save = async () => {
    if (!form) return;
    setBusy("save");
    setMessage(null);
    try {
      const result = await api.saveSettings({
        provider: form.provider,
        base_url: form.base_url,
        model: form.model,
        temperature: Number(form.temperature) || 0.3,
        max_tokens: Number(form.max_tokens) || 300,
        api_key: form.api_key.trim() || undefined,
        persist: true,
      });
      setTone("ok");
      setMessage(
        result.persisted
          ? `已保存到 ${data?.env_file ?? "backend/.env"}${result.api_key_updated ? "（含 API Key）" : ""}，重启后端后依然生效。`
          : "已应用到当前运行中的服务（未写入 .env）。",
      );
      patch({ api_key: "" });
      reload();
    } catch (err) {
      setTone("bad");
      setMessage((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const runTest = async () => {
    setBusy("test");
    setMessage(null);
    try {
      const result = await api.llmTest();
      setTest(result);
      setTone(result.ok ? "ok" : "bad");
      setMessage(result.message);
    } catch (err) {
      setTone("bad");
      setMessage((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <>
        <div className="px-5 py-8 lg:px-[33px]">
          <div className="skeleton h-[320px]" />
        </div>
      </>
    );
  }

  if (error || !data || !form) {
    return (
      <>
        <div className="px-5 py-8 lg:px-[33px]">
          <ErrorState message={error} onRetry={reload} hint="设置页需要后端在线" />
        </div>
      </>
    );
  }

  return (
    <>
      <div className="px-5 pb-12 pt-8 lg:px-[33px]">
        <div className="mb-1 flex items-center gap-2">
          <GearIcon size={20} className="text-flare" />
          <h1 className="text-[28px] font-black">系统设置</h1>
        </div>
        <p className="mb-6 text-[15px] text-ink-mute">配置 LLM 服务与相关参数</p>

        <section className="card p-6">
          <div className="mb-5 flex items-center gap-2">
            <span className="text-[16px]">🔌</span>
            <h2 className="text-[18px] font-bold">LLM 配置</h2>
            <span
              className={`chip ml-2 ${data.config.api_key_set ? "bg-go/10 text-go" : "bg-gold/20 text-[#B2750A]"}`}
            >
              {data.config.api_key_set ? "已配置 Key" : "未配置 Key（AI 文案走算法兜底）"}
            </span>
          </div>

          <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            <label className="flex items-center gap-3">
              <span className="w-[92px] shrink-0 text-[14px] font-medium text-ink-soft">LLM 提供商</span>
              <select
                className="field flex-1"
                value={PROVIDERS.some((p) => p.value === form.provider) ? form.provider : PROVIDERS[0].value}
                onChange={(event) => patch({ provider: event.target.value })}
              >
                {PROVIDERS.map((provider) => (
                  <option key={provider.value} value={provider.value}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-start gap-3">
              <span className="w-[92px] shrink-0 pt-2.5 text-[14px] font-medium text-ink-soft">API Key</span>
              <div className="relative flex-1">
                <input
                  className="field flex-1 pr-10"
                  type={showKey ? "text" : "password"}
                  value={form.api_key}
                  placeholder={data.config.api_key_masked || "请输入 API Key"}
                  autoComplete="off"
                  onChange={(event) => patch({ api_key: event.target.value })}
                />
                <button
                  type="button"
                  onClick={() => setShowKey((value) => !value)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink-mute"
                  aria-label={showKey ? "隐藏 API Key" : "显示 API Key"}
                >
                  <EyeIcon size={16} open={!showKey} />
                </button>
              </div>
              <span className="mt-1 block text-[11px] text-ink-faint">
                {data.config.api_key_set
                  ? `当前已保存 ${data.config.api_key_masked}，留空表示不修改`
                  : "只写入后端 .env，不会出现在前端与接口响应里"}
              </span>
            </label>

            <label className="flex items-center gap-3">
              <span className="w-[92px] shrink-0 text-[14px] font-medium text-ink-soft">Base URL</span>
              <input
                className="field flex-1"
                value={form.base_url}
                onChange={(event) => patch({ base_url: event.target.value })}
              />
            </label>

            <label className="flex items-center gap-3">
              <span className="w-[92px] shrink-0 text-[14px] font-medium text-ink-soft">Temperature</span>
              <input
                className="field flex-1"
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={form.temperature}
                onChange={(event) => patch({ temperature: event.target.value })}
              />
            </label>

            <label className="flex items-center gap-3">
              <span className="w-[92px] shrink-0 text-[14px] font-medium text-ink-soft">Model</span>
              <input
                className="field flex-1"
                value={form.model}
                onChange={(event) => patch({ model: event.target.value })}
              />
            </label>

            <label className="flex items-center gap-3">
              <span className="w-[92px] shrink-0 text-[14px] font-medium text-ink-soft">Max Tokens</span>
              <input
                className="field flex-1"
                type="number"
                min="16"
                max="4096"
                value={form.max_tokens}
                onChange={(event) => patch({ max_tokens: event.target.value })}
              />
            </label>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 md:justify-end">
            <button type="button" className="btn-primary" onClick={save} disabled={busy !== null}>
              {busy === "save" ? "保存中…" : "保存配置"}
            </button>
            <button type="button" className="btn-ghost" onClick={runTest} disabled={busy !== null}>
              <RefreshIcon size={15} className={busy === "test" ? "animate-spin" : ""} />
              {busy === "test" ? "测试中…" : "测试连接"}
            </button>
            {message ? (
              <span
                className={`text-[12px] ${tone === "ok" ? "text-go" : tone === "bad" ? "text-brand" : "text-ink-mute"}`}
              >
                {message}
              </span>
            ) : null}
          </div>

          {test ? (
            <div className="mt-4 rounded-xl bg-rail px-4 py-3 text-[12px] text-ink-mute">
              <div>模型：{test.model ?? data.config.model}</div>
              <div>延迟：{test.latency_ms ? `${test.latency_ms} ms` : "—"}</div>
              {test.echo ? <div className="truncate">返回：{test.echo}</div> : null}
            </div>
          ) : null}
        </section>

        <section className="card mt-5 p-6">
          <div className="mb-4 flex items-center gap-2">
            <span className="text-[16px]">⚙️</span>
            <h2 className="text-[18px] font-bold">系统信息</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "统计截至",
                value: meta?.data_through
                  ? `${meta.data_through}${meta.data_lag_days ? `（滞后 ${meta.data_lag_days} 天）` : ""}`
                  : "—",
              },
              { label: "当前版本", value: data.version },
              { label: "运行环境", value: data.environment },
              {
                label: "数据来源",
                // 只报配置的数据源，不替数据质量背书：是不是演示数据由库里的实际内容决定，
                // 上面「含演示数据」那颗标记才是结论。
                value:
                  data.data_source === "bilibili"
                    ? "Bilibili"
                    : data.data_source === "mixed"
                      ? "Bilibili + 演示数据混合"
                      : "演示数据（Mock）",
              },
            ].map((item) => (
              <div key={item.label} className="rounded-xl bg-rail px-4 py-3">
                <div className="text-[13px] text-ink-mute">{item.label}</div>
                <div className="mt-1 text-[16px] font-bold">{item.value}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-3 rounded-xl border border-dashed border-line px-4 py-3">
            <img src="/brand/mascot-sign.png" width={44} alt="" className="select-none" />
            <div className="brush-title text-[15px] font-bold leading-snug">
              一起发现
              <br />
              更多有趣的梗！
            </div>
            <div className="ml-auto text-right text-[11px] leading-relaxed text-ink-faint">
              热榜 {meta?.certified_count ?? 0} 个 / 梗库 {meta?.library_count ?? 0} 个
              <br />
              未入池 {meta?.candidate_count ?? 0} 个 · 分析窗口 {meta?.window_days ?? 0} 天 · 认证窗口{" "}
              {meta?.transparency?.cert_window_days ?? 90} 天
            </div>
          </div>
        </section>

        <TransparencyFooter meta={meta} />
      </div>
    </>
  );
}
