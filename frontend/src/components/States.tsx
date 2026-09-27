import { ApiError } from "@/api/client";

export function LoadingCards({ count = 5 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="card p-3">
          <div className="skeleton h-[92px] w-full" />
          <div className="skeleton mt-3 h-4 w-2/3" />
          <div className="skeleton mt-2 h-5 w-1/3" />
          <div className="skeleton mt-3 h-8 w-full" />
        </div>
      ))}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  hint,
}: {
  message?: string | null;
  onRetry?: () => void;
  hint?: string;
}) {
  return (
    <div className="card flex flex-col items-start gap-3 p-6">
      <div className="flex items-center gap-2">
        <span className="text-xl">😵</span>
        <h3 className="text-[16px] font-bold">数据没拿到</h3>
      </div>
      <p className="text-[13px] leading-relaxed text-ink-mute">
        {message ?? "未知错误"}
        {hint ? <span className="ml-1 text-ink-faint">（{hint}）</span> : null}
      </p>
      <p className="text-[12px] text-ink-faint">
        后端启动命令：<code className="rounded bg-dusk/10 px-1.5 py-0.5">cd backend && uvicorn app.main:app --port 8000</code>
      </p>
      {onRetry ? (
        <button type="button" className="btn-ghost" onClick={onRetry}>
          重新加载
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="card flex flex-col items-center gap-2 p-10 text-center">
      <span className="text-3xl">🫥</span>
      <h3 className="text-[15px] font-bold">{title}</h3>
      {description ? <p className="text-[13px] text-ink-mute">{description}</p> : null}
    </div>
  );
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error) return error.message;
  return "未知错误";
}

/** 演示数据标记：不允许把 Mock 伪装成实时抓取结果。 */
export function DemoBadge({ isDemo, source }: { isDemo: boolean; source: string }) {
  if (!isDemo) {
    return (
      <span className="chip hidden bg-go/10 text-go sm:inline-flex">
        <span className="h-1.5 w-1.5 rounded-full bg-go" />
        B站真实数据
      </span>
    );
  }
  return (
    <span
      className="chip hidden bg-gold/20 text-[#B2750A] sm:inline-flex"
      title="当前展示的是演示数据，不是实时抓取的 B 站数据"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-gold" />
      演示数据 · {source === "mock" ? "Mock" : source}
    </span>
  );
}
