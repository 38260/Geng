import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { SectionHeader, TransparencyFooter } from "@/components/Sections";
import { ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import { useMeta } from "@/hooks/useAppData";
import { STAGE_STYLE, percent, growthClass } from "@/utils/format";

/** 热度趋势：一屏看完所有梗的相对位置（不做 BI 大屏）。 */
export default function Trends() {
  const { meta } = useMeta();
  const { data, loading, error, reload } = useAsync(() => api.memes({ limit: 100 }), []);
  const items = data?.items ?? [];
  const max = items.length ? Math.max(...items.map((item) => item.hotness)) : 100;

  return (
    <>
      <div className="px-5 pb-12 pt-8 lg:px-[33px]">
        <SectionHeader emoji="📊" title="热度趋势" />
        <p className="-mt-2 mb-5 text-[13px] text-ink-mute">
          热度为赶梗潮自定义指数（0-100，滚动 7 天窗口），增幅口径是最近 7 天相对前 7 天。
        </p>

        {loading ? (
          <LoadingCards count={6} />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-left text-[13px]">
              <thead className="border-b border-line bg-rail text-[12px] text-ink-mute">
                <tr>
                  <th className="w-12 px-4 py-2.5 font-medium">#</th>
                  <th className="px-2 py-2.5 font-medium">梗</th>
                  <th className="w-[38%] px-2 py-2.5 font-medium">热度</th>
                  <th className="px-2 py-2.5 font-medium">阶段</th>
                  <th className="px-2 py-2.5 text-right font-medium">7天增幅</th>
                  <th className="px-4 py-2.5 text-right font-medium">赶梗</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, index) => (
                  <tr key={item.id} className="border-b border-line/70 last:border-0 hover:bg-rail/70">
                    <td className="tabular px-4 py-2.5 text-ink-faint">{index + 1}</td>
                    <td className="px-2 py-2.5">
                      <Link to={`/meme/${item.id}`} className="font-semibold hover:text-flare">
                        {item.thumbnail.emoji} {item.name}
                      </Link>
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-full max-w-[220px] overflow-hidden rounded-full bg-line">
                          <div
                            className={`h-full rounded-full ${STAGE_STYLE[item.stage].dot}`}
                            style={{ width: `${Math.max(3, (item.hotness / max) * 100)}%` }}
                          />
                        </div>
                        <span className="tabular w-9 text-right font-bold">{Math.round(item.hotness)}</span>
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      <span className={`chip ${STAGE_STYLE[item.stage].chip}`}>{item.nickname}</span>
                    </td>
                    <td className={`tabular px-2 py-2.5 text-right font-semibold ${growthClass(item.discussion_growth)}`}>
                      {percent(item.discussion_growth)}
                    </td>
                    <td className="px-4 py-2.5 text-right text-[12px] text-ink-mute">{item.catch_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <TransparencyFooter meta={meta} />
      </div>
    </>
  );
}
