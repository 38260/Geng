import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { DemoBadge } from "@/components/States";
import { ArrowLeftIcon, CalendarIcon, SearchIcon } from "@/components/icons";
import { useMeta } from "@/hooks/useAppData";
import { formatDateTime } from "@/utils/format";

function DateChip({ updatedAt }: { updatedAt?: string | null }) {
  const date = updatedAt ? new Date(updatedAt) : new Date();
  const valid = !Number.isNaN(date.getTime());
  const iso = valid ? formatDateTime(updatedAt ?? new Date().toISOString()).slice(0, 10) : "—";
  return (
    <div className="hidden items-center gap-2 rounded-xl px-2 py-1 text-right sm:flex">
      <CalendarIcon size={18} className="text-flare" />
      <div className="leading-tight">
        <div className="tabular text-[13px] font-semibold text-ink">{iso}</div>
        <div className="text-[11px] text-ink-faint">今日更新</div>
      </div>
    </div>
  );
}

function Avatar() {
  return (
    <div
      className="grid h-9 w-9 place-items-center rounded-full bg-brand-soft text-[15px] ring-1 ring-line"
      title="演示头像（V1 不做登录）"
    >
      🐧
    </div>
  );
}

export function Header({
  search,
  onSearch,
}: {
  search?: string;
  onSearch?: (value: string) => void;
}) {
  const { meta } = useMeta();
  const [value, setValue] = useState(search ?? "");
  const navigate = useNavigate();

  useEffect(() => setValue(search ?? ""), [search]);

  return (
    <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-canvas/85 px-4 py-3 backdrop-blur-sm lg:px-7">
      <div className="relative w-full max-w-[420px]">
        <SearchIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
        <input
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            onSearch?.(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && value.trim()) navigate(`/library?q=${encodeURIComponent(value.trim())}`);
          }}
          placeholder="搜索梗名、别名、关键词…"
          className="w-full rounded-full border border-line bg-surface py-2.5 pl-10 pr-4 text-[13px] outline-none transition placeholder:text-ink-faint focus:border-flare/50 focus:ring-2 focus:ring-flare/15"
        />
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
        {meta ? <DemoBadge isDemo={meta.is_demo} source={meta.data_source} /> : null}
        <DateChip updatedAt={meta?.data_updated_at} />
        <div className="hidden h-7 w-px bg-line sm:block" />
        <Avatar />
      </div>
    </header>
  );
}

export function DetailTopBar({ updatedAt }: { updatedAt?: string | null }) {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-canvas/85 px-4 py-3 backdrop-blur-sm lg:px-7">
      <button type="button" onClick={() => navigate(-1)} className="link-quiet">
        <ArrowLeftIcon size={17} />
        返回
      </button>
      <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
        <DateChip updatedAt={updatedAt} />
        <div className="hidden h-7 w-px bg-line sm:block" />
        <Avatar />
      </div>
    </header>
  );
}
